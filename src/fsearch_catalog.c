/* Immutable base + bounded copy-on-write overlay, with explicit compaction replay.
 * Query/mutation paths never probe indexed storage. Private checkpoint cache
 * descriptors provide bounded persistence; GLib locks protect ownership.
 * GPL-2.0-or-later. */
#include "fsearch_catalog.h"
#include "fsearch_catalog_query.h"
#include "fsearch_headless_signature.h"
#include "fsearch_file_utils.h"
#include "fsearch_string_utils.h"
#include "fsearch_query.h"
#include "fsearch_database_entry.h"
#include <stdlib.h>
#include <string.h>
#include <stdalign.h>
#include <errno.h>
#include <sys/stat.h>
#include <unistd.h>

#define MAX_DEPTH 256u
#define MAX_NAME 4096u

typedef struct {
    gint refs, views;
    GMutex lock;
    size_t used, reserved, peak, limit;
} Budget;
typedef union {
    struct { Budget *budget; size_t bytes; } allocation;
    max_align_t alignment;
} Allocation;
typedef struct { uint32_t id, parent, offset, kind; } Packed;
typedef struct {
    gint refs;
    unsigned count;
    size_t names_size;
    Packed *entries;
    uint32_t *namespace_order, *name_order, *root_order;
    unsigned root_count;
    uint64_t *signatures;
    size_t signature_stride;
    char *names;
} Base;
typedef struct {
    gint refs;
    uint32_t id, parent, kind;
    char name[];
} Delta;
struct FsearchCatalogView {
    gint refs;
    Budget *budget;
    Base *base;
    uint64_t sequence, generation;
    unsigned count;
    Delta *delta[]; /* sorted by immutable ID, never by changing path */
};
struct FsearchCatalogBuild {
    FsearchCatalogView *capture;
    Base *replacement;
    Budget *budget;
    size_t reservation;
    unsigned count, limit;
    Delta **replay;
    bool failed, ran, validated, published;
    const char *reason;
};
struct FsearchCatalog {
    GMutex lock;
    Budget *budget;
    FsearchCatalogView *current;
    FsearchCatalogBuild *build;
    FsearchCatalogLimits limits;
    uint32_t highwater;
    const char *deferred;
    bool closed;
};

static bool fail(const char **error, const char *reason) { if (error) *error=reason; return false; }
static void budget_ref(Budget *b) { g_atomic_int_inc(&b->refs); }
static void budget_unref(Budget *b) {
    if (g_atomic_int_dec_and_test(&b->refs)) { g_mutex_clear(&b->lock); free(b); }
}
/* Account payload, allocation header and a conservative malloc metadata allowance.
 * Process/cgroup measurements remain authoritative for total resident memory. */
static size_t cost(size_t n) { return n + sizeof(Allocation) + 32; }
static void *allocate(Budget *b,size_t n,size_t *reservation) {
    if (n>SIZE_MAX-sizeof(Allocation)-32) return NULL;
    size_t bytes=cost(n), take=reservation ? MIN(*reservation,bytes) : 0;
    g_mutex_lock(&b->lock);
    if (bytes>b->limit-b->used-b->reserved+take) { g_mutex_unlock(&b->lock); return NULL; }
    Allocation *a=calloc(1,n+sizeof(Allocation));
    if (!a) { g_mutex_unlock(&b->lock); return NULL; }
    b->reserved-=take;if(reservation)*reservation-=take;
    b->used+=bytes;b->peak=MAX(b->peak,b->used+b->reserved);budget_ref(b);
    g_mutex_unlock(&b->lock);a->allocation.budget=b;a->allocation.bytes=bytes;return a+1;
}
static void release(void *p) {
    if (!p) return;
    Allocation *a=(Allocation*)p-1;Budget*b=a->allocation.budget;
    g_mutex_lock(&b->lock);b->used-=a->allocation.bytes;g_mutex_unlock(&b->lock);
    free(a);budget_unref(b);
}
static void unreserve(FsearchCatalogBuild *t) {
    g_mutex_lock(&t->budget->lock);t->budget->reserved-=t->reservation;t->reservation=0;g_mutex_unlock(&t->budget->lock);
}
static Base *base_ref(Base *b) { g_atomic_int_inc(&b->refs);return b; }
static void base_unref(Base *b) { if(g_atomic_int_dec_and_test(&b->refs))release(b); }
static Delta *delta_ref(Delta *d) { g_atomic_int_inc(&d->refs);return d; }
static void delta_unref(Delta *d) { if(g_atomic_int_dec_and_test(&d->refs))release(d); }
FsearchCatalogView *fsearch_catalog_view_ref(FsearchCatalogView *v) { if(v)g_atomic_int_inc(&v->refs);return v; }
void fsearch_catalog_view_unref(FsearchCatalogView *v) {
    if(!v||!g_atomic_int_dec_and_test(&v->refs))return;
    for(unsigned i=0;i<v->count;i++)delta_unref(v->delta[i]);
    base_unref(v->base);g_atomic_int_add(&v->budget->views,-1);release(v);
}
static FsearchCatalogView *view_new(Budget*b,Base*base,unsigned n,size_t*reservation) {
    FsearchCatalogView*v=allocate(b,sizeof(*v)+(size_t)n*sizeof(Delta*),reservation);
    if(!v)return NULL;
    v->refs=1;v->budget=b;v->base=base_ref(base);g_atomic_int_inc(&b->views);return v;
}
static unsigned delta_position(FsearchCatalogView*v,uint32_t id) {
    unsigned lo=0,hi=v->count;
    while(lo<hi){unsigned m=lo+(hi-lo)/2;if(v->delta[m]->id<id)lo=m+1;else hi=m;}return lo;
}
static bool raw_get(FsearchCatalogView*v,uint32_t id,FsearchCatalogEntry*out) {
    unsigned p=delta_position(v,id);
    if(p<v->count&&v->delta[p]->id==id){Delta*d=v->delta[p];*out=(FsearchCatalogEntry){d->id,d->parent,d->kind,d->name};return true;}
    if(id<v->base->count&&v->base->entries[id].id==id){Packed*r=&v->base->entries[id];*out=(FsearchCatalogEntry){r->id,r->parent,r->kind,v->base->names+r->offset};return true;}
    unsigned lo=0,hi=v->base->count;
    while(lo<hi){unsigned m=lo+(hi-lo)/2;if(v->base->entries[m].id<id)lo=m+1;else hi=m;}
    if(lo==v->base->count||v->base->entries[lo].id!=id)return false;
    Packed*r=&v->base->entries[lo];*out=(FsearchCatalogEntry){r->id,r->parent,r->kind,v->base->names+r->offset};return true;
}
bool fsearch_catalog_view_get(FsearchCatalogView*v,uint32_t id,FsearchCatalogEntry*out) {
    FsearchCatalogEntry e;
    if(!v||!raw_get(v,id,&e)||!e.kind)return false;
    *out=e;
    for(unsigned depth=0;depth<MAX_DEPTH;depth++) {
        if(e.parent==e.id)return e.kind==FSEARCH_CATALOG_FOLDER&&e.name[0]=='/';
        if(!raw_get(v,e.parent,&e)||e.kind!=FSEARCH_CATALOG_FOLDER)return false;
    }
    return false;
}
char *fsearch_catalog_view_path(FsearchCatalogView*v,uint32_t id) {
    FsearchCatalogEntry e;if(!fsearch_catalog_view_get(v,id,&e))return NULL;
    const char*names[MAX_DEPTH];unsigned n=0;
    for(;;){if(n==MAX_DEPTH)return NULL;names[n++]=e.name;if(e.parent==e.id)break;if(!raw_get(v,e.parent,&e))return NULL;}
    GString*s=g_string_new(NULL);
    while(n){if(s->len&&s->str[s->len-1]!='/')g_string_append_c(s,'/');g_string_append(s,names[--n]);}
    return g_string_free(s,false);
}
uint64_t fsearch_catalog_view_sequence(FsearchCatalogView*v){return v->sequence;}
uint64_t fsearch_catalog_view_generation(FsearchCatalogView*v){return v->generation;}
bool fsearch_catalog_view_visit(FsearchCatalogView*v,FsearchCatalogVisitor visitor,void*data) {
    unsigned b=0,d=0;
    while(b<v->base->count||d<v->count){uint32_t id;
        if(d==v->count||(b<v->base->count&&v->base->entries[b].id<v->delta[d]->id))id=v->base->entries[b++].id;
        else {id=v->delta[d++]->id;if(b<v->base->count&&v->base->entries[b].id==id)b++;}
        FsearchCatalogEntry e;if(fsearch_catalog_view_get(v,id,&e)&&!visitor(&e,data))return false;
    }
    return true;
}
static int packed_id(const void*a,const void*b){uint32_t x=((const Packed*)a)->id,y=((const Packed*)b)->id;return(x>y)-(x<y);}
static int namespace_cmp(const void*a,const void*b,void*data) {
    Base*base=data;Packed*x=&base->entries[*(const uint32_t*)a],*y=&base->entries[*(const uint32_t*)b];
    if(x->parent!=y->parent)return(x->parent>y->parent)-(x->parent<y->parent);
    return strcmp(base->names+x->offset,base->names+y->offset);
}
static size_t signature_bytes(size_t count) {
    size_t stride=(count+63)/64;
    return stride<=SIGNATURE_MAX_BYTES/(192*sizeof(uint64_t))?stride*192*sizeof(uint64_t):0;
}
static size_t base_bytes(size_t count,size_t names,unsigned roots) {
    size_t arrays=count*(sizeof(Packed)+2*sizeof(uint32_t))+(size_t)roots*sizeof(uint32_t);
    return sizeof(Base)+((arrays+7)&~(size_t)7)+signature_bytes(count)+names;
}
static Base *base_allocate(Budget*b,unsigned n,size_t names,unsigned roots,size_t*reservation) {
    if(names>UINT32_MAX||n>(SIZE_MAX-sizeof(Base)-names-SIGNATURE_MAX_BYTES)/(sizeof(Packed)+2*sizeof(uint32_t)))return NULL;
    Base*x=allocate(b,base_bytes(n,names,roots),reservation);
    if(!x)return NULL;
    x->refs=1;x->count=n;x->names_size=names;x->entries=(Packed*)(x+1);
    x->namespace_order=(uint32_t*)(x->entries+n);x->name_order=x->namespace_order+n;
    x->root_order=x->name_order+n;x->root_count=roots;
    size_t arrays=(size_t)n*(sizeof(Packed)+2*sizeof(uint32_t))+(size_t)roots*sizeof(uint32_t);
    char*aligned=(char*)(x+1)+((arrays+7)&~(size_t)7);
    size_t bytes=signature_bytes(n);x->signature_stride=bytes?(n+63)/64:0;
    x->signatures=bytes?(uint64_t*)aligned:NULL;x->names=aligned+bytes;return x;
}
static int name_cmp(const void*a,const void*b,void*data) {
    Base*base=data;Packed*x=&base->entries[*(const uint32_t*)a],*y=&base->entries[*(const uint32_t*)b];
    if(x->kind!=y->kind)return(x->kind>y->kind)-(x->kind<y->kind);
    return fsearch_file_utils_cmp_paths(base->names+x->offset,base->names+y->offset);
}
static void base_sort(Base*b) {
    bool sorted=true;for(unsigned i=1;i<b->count;i++)if(b->entries[i-1].id>b->entries[i].id){sorted=false;break;}
    if(!sorted)qsort(b->entries,b->count,sizeof(Packed),packed_id);
    unsigned roots=0;
    for(unsigned i=0;i<b->count;i++){b->namespace_order[i]=b->name_order[i]=i;if(b->entries[i].parent==b->entries[i].id)b->root_order[roots++]=i;}
    g_assert(roots==b->root_count);
    g_qsort_with_data(b->namespace_order,b->count,sizeof(uint32_t),namespace_cmp,b);
    g_qsort_with_data(b->name_order,b->count,sizeof(uint32_t),name_cmp,b);
    FsearchUtfBuilder builder={0};
    for(unsigned rank=0;b->signatures&&rank<b->count;rank++) {
        Packed*r=&b->entries[b->name_order[rank]];const char*name=b->names+r->offset;uint64_t bits[3];signature_text(name,bits);
        if(!signature_ascii(name)) {
            g_autofree char*normalized=normalized_utf8(&builder,name);
            if(normalized){uint64_t folded[3];signature_text(normalized,folded);for(unsigned w=0;w<3;w++)bits[w]|=folded[w];}
            else for(unsigned w=0;w<3;w++)bits[w]=UINT64_MAX;
        }
        for(unsigned w=0;w<3;w++)for(uint64_t set=bits[w];set;set&=set-1){unsigned bit=__builtin_ctzll(set);b->signatures[(w*64+bit)*b->signature_stride+rank/64]|=UINT64_C(1)<<(rank%64);}
    }
    fsearch_utf_builder_clear(&builder);
}
static bool basename_valid(const char*name) {
    return name&&*name&&strnlen(name,MAX_NAME+1)<=MAX_NAME&&!strchr(name,'/')&&strcmp(name,".")&&strcmp(name,"..");
}
static bool collision(FsearchCatalogView*v,uint32_t id,uint32_t parent,const char*name) {
    for(unsigned i=0;i<v->count;i++){Delta*d=v->delta[i];if(d->id!=id&&d->kind&&d->parent==parent&&!strcmp(d->name,name))return true;}
    Base*b=v->base;unsigned lo=0,hi=b->count;
    while(lo<hi){unsigned m=lo+(hi-lo)/2;Packed*r=&b->entries[b->namespace_order[m]];int cmp=r->parent==parent?strcmp(b->names+r->offset,name):(r->parent>parent?1:-1);if(cmp<0)lo=m+1;else hi=m;}
    if(lo==b->count)return false;
    Packed*r=&b->entries[b->namespace_order[lo]];
    return r->id!=id&&r->kind&&r->parent==parent&&!strcmp(b->names+r->offset,name)
           &&!(delta_position(v,r->id)<v->count&&v->delta[delta_position(v,r->id)]->id==r->id);
}
FsearchCatalog *fsearch_catalog_new(const FsearchCatalogEntry*entries,unsigned count,const FsearchCatalogLimits*limits,const char**error) {
    if(!entries||!count||!limits||!limits->memory_limit||!limits->overlay_limit||!limits->replay_limit||limits->overlay_limit>65536||limits->replay_limit>65536||limits->view_limit<3||limits->view_limit>64){fail(error,"invalid_limits");return NULL;}
    size_t names=0;uint32_t high=0;unsigned roots=0;
    for(unsigned i=0;i<count;i++){
        const FsearchCatalogEntry*e=&entries[i];size_t n=e->name?strnlen(e->name,MAX_NAME+1):MAX_NAME+1;
        if(n>MAX_NAME||!n||e->kind<FSEARCH_CATALOG_FILE||e->kind>FSEARCH_CATALOG_FOLDER
           ||(e->parent!=e->id&&!basename_valid(e->name))||(e->parent==e->id&&(e->kind!=FSEARCH_CATALOG_FOLDER||e->name[0]!='/'))){fail(error,"invalid_entry");return NULL;}
        names+=n+1;high=MAX(high,e->id);if(e->parent==e->id)roots++;
    }
    Budget*b=calloc(1,sizeof(*b));if(!b){fail(error,"allocation_failed");return NULL;}b->refs=1;b->limit=limits->memory_limit;g_mutex_init(&b->lock);
    FsearchCatalog*c=allocate(b,sizeof(*c),NULL);Base*base=base_allocate(b,count,names,roots,NULL);
    if(!c||!base){release(c);if(base)base_unref(base);budget_unref(b);fail(error,"memory_budget");return NULL;}
    c->budget=b;c->limits=*limits;c->highwater=high;g_mutex_init(&c->lock);
    size_t offset=0;for(unsigned i=0;i<count;i++){const FsearchCatalogEntry*e=&entries[i];base->entries[i]=(Packed){e->id,e->parent,offset,e->kind};strcpy(base->names+offset,e->name);offset+=strlen(e->name)+1;}
    base_sort(base);c->current=view_new(b,base,0,NULL);base_unref(base);
    if(!c->current){fsearch_catalog_free(c);fail(error,"memory_budget");return NULL;}
    bool valid=c->current->base->entries[0].id==0&&c->current->base->entries[0].parent==0;
    for(unsigned i=0;i<count&&valid;i++) {
        Packed*r=&c->current->base->entries[i];FsearchCatalogEntry e;
        if((i&&r->id==c->current->base->entries[i-1].id)||!fsearch_catalog_view_get(c->current,r->id,&e))valid=false;
    }
    for(unsigned i=1;i<count&&valid;i++)if(!namespace_cmp(&c->current->base->namespace_order[i-1],&c->current->base->namespace_order[i],c->current->base))valid=false;
    if(!valid){fsearch_catalog_free(c);fail(error,"invalid_tree");return NULL;}return c;
}
FsearchCatalogView *fsearch_catalog_acquire(FsearchCatalog*c) {
    g_mutex_lock(&c->lock);FsearchCatalogView*v=c->closed?NULL:fsearch_catalog_view_ref(c->current);g_mutex_unlock(&c->lock);return v;
}
void fsearch_catalog_close(FsearchCatalog*c){g_mutex_lock(&c->lock);c->closed=true;if(c->build){c->build->failed=true;c->build->reason="closed";}g_mutex_unlock(&c->lock);}
void fsearch_catalog_free(FsearchCatalog*c) {
    if(!c)return;
    fsearch_catalog_close(c);g_assert(c->build==NULL);fsearch_catalog_view_unref(c->current);
    Budget*b=c->budget;g_mutex_clear(&c->lock);release(c);budget_unref(b);
}
static bool mutate(FsearchCatalog*c,uint64_t sequence,uint32_t id,uint32_t parent,FsearchCatalogKind kind,const char*name,bool create,const char**error) {
    FsearchCatalogView*v=c->current;FsearchCatalogEntry old,p;
    if(c->closed)return fail(error,"closed");
    if(v->sequence==UINT64_MAX)return fail(error,"sequence_limit");
    if(sequence!=v->sequence+1)return fail(error,"sequence_gap");
    if(!create&&(!fsearch_catalog_view_get(v,id,&old)))return fail(error,"retired_identity");
    if(!create&&old.parent==old.id)return fail(error,"immutable_root");
    if(kind>FSEARCH_CATALOG_FOLDER||kind<FSEARCH_CATALOG_DELETED)return fail(error,"invalid_kind");
    if(kind) {
        if(!basename_valid(name)||!fsearch_catalog_view_get(v,parent,&p)||p.kind!=FSEARCH_CATALOG_FOLDER)return fail(error,"invalid_parent_or_name");
        if(!create&&old.kind!=kind)return fail(error,"type_transition_requires_new_identity");
        unsigned depth=0;for(;;){if(p.id==id)return fail(error,"cycle");if(p.parent==p.id)break;if(++depth>=MAX_DEPTH-1)return fail(error,"depth_limit");if(!raw_get(v,p.parent,&p))return fail(error,"invalid_parent");}
        if(collision(v,id,parent,name))return fail(error,"namespace_collision");
    }
    unsigned at=delta_position(v,id);bool replace=at<v->count&&v->delta[at]->id==id;
    if(!replace&&v->count==c->limits.overlay_limit){c->deferred="overlay_budget";return fail(error,c->deferred);}
    if(g_atomic_int_get(&c->budget->views)>=(int)c->limits.view_limit){c->deferred="reader_budget";return fail(error,c->deferred);}
    Delta*d=allocate(c->budget,sizeof(*d)+strlen(kind?name:"")+1,NULL);
    FsearchCatalogView*next=view_new(c->budget,v->base,v->count+!replace,NULL);
    if(!d||!next){release(d);if(next)fsearch_catalog_view_unref(next);c->deferred="memory_budget";return fail(error,c->deferred);}
    d->refs=1;d->id=id;d->parent=parent;d->kind=kind;strcpy(d->name,kind?name:"");
    next->sequence=sequence;next->generation=v->generation;next->count=v->count+!replace;
    for(unsigned src=0,dst=0;dst<next->count;dst++) {
        if(dst==at){next->delta[dst]=d;if(replace)src++;}
        else next->delta[dst]=delta_ref(v->delta[src++]);
    }
    if(c->build&&!c->build->failed) {
        FsearchCatalogBuild*t=c->build;
        if(t->count==t->limit){t->failed=true;t->reason="replay_overflow";c->deferred=t->reason;}
        else t->replay[t->count++]=delta_ref(d);
    }
    c->current=next;if(create)c->highwater=id;
    if(!c->build||!c->build->failed)c->deferred=NULL;
    fsearch_catalog_view_unref(v);return true;
}
bool fsearch_catalog_create(FsearchCatalog*c,uint64_t sequence,uint32_t parent,FsearchCatalogKind kind,const char*name,uint32_t*id,const char**error) {
    g_mutex_lock(&c->lock);bool ok;
    if(!kind||c->highwater==UINT32_MAX)ok=fail(error,"identity_limit");
    else{uint32_t next=c->highwater+1;ok=mutate(c,sequence,next,parent,kind,name,true,error);if(ok&&id)*id=next;}
    g_mutex_unlock(&c->lock);return ok;
}
bool fsearch_catalog_change(FsearchCatalog*c,uint64_t seq,uint32_t id,uint32_t parent,FsearchCatalogKind kind,const char*name,const char**error) {
    g_mutex_lock(&c->lock);bool ok=mutate(c,seq,id,parent,kind,name,false,error);g_mutex_unlock(&c->lock);return ok;
}
void fsearch_catalog_status(FsearchCatalog*c,FsearchCatalogStatus*s) {
    g_mutex_lock(&c->lock);g_mutex_lock(&c->budget->lock);
    *s=(FsearchCatalogStatus){.sequence=c->current->sequence,.generation=c->current->generation,
        .accounted_bytes=c->budget->used,.reserved_bytes=c->budget->reserved,.peak_bytes=c->budget->peak,
        .live_views=g_atomic_int_get(&c->budget->views),.overlay_entries=c->current->count,
        .deferred_reason=c->deferred,.building=c->build!=NULL,.closed=c->closed};
    g_mutex_unlock(&c->budget->lock);g_mutex_unlock(&c->lock);
}
FsearchCatalogBuild *fsearch_catalog_compact_begin(FsearchCatalog*c,const char**error) {
    g_mutex_lock(&c->lock);
    if(c->closed||c->build){fail(error,c->closed?"closed":"builder_busy");g_mutex_unlock(&c->lock);return NULL;}
    FsearchCatalogBuild*t=allocate(c->budget,sizeof(*t)+(size_t)c->limits.replay_limit*sizeof(Delta*),NULL);
    if(!t){c->deferred="memory_budget";fail(error,c->deferred);g_mutex_unlock(&c->lock);return NULL;}
    FsearchCatalogView*v=c->current;size_t names=v->base->names_size;
    for(unsigned i=0;i<v->count;i++)names+=strlen(v->delta[i]->name)+1;
    size_t count=(size_t)v->base->count+v->count;
    size_t signature_reserve=signature_bytes(count)?0:SIGNATURE_MAX_BYTES;
    size_t needed=cost(base_bytes(count,names,v->base->root_count)+signature_reserve)+(count*sizeof(Packed)+1024*1024) /* reserve sort/ICU scratch too */
                  +cost(sizeof(FsearchCatalogView)+(size_t)c->limits.overlay_limit*sizeof(Delta*));
    g_mutex_lock(&c->budget->lock);
    bool fits=needed<=c->budget->limit-c->budget->used-c->budget->reserved;
    if(fits){c->budget->reserved+=needed;c->budget->peak=MAX(c->budget->peak,c->budget->used+c->budget->reserved);}
    g_mutex_unlock(&c->budget->lock);
    if(!fits){release(t);c->deferred="memory_budget";fail(error,c->deferred);g_mutex_unlock(&c->lock);return NULL;}
    t->budget=c->budget;t->reservation=needed;t->capture=fsearch_catalog_view_ref(v);
    t->replay=(Delta**)(t+1);t->limit=c->limits.replay_limit;c->build=t;c->deferred=NULL;
    g_mutex_unlock(&c->lock);return t;
}
typedef struct { unsigned count,roots;size_t names;Base*base; } Collector;
static bool collect(const FsearchCatalogEntry*e,void*data) {
    Collector*x=data;
    if(x->base){x->base->entries[x->count]=(Packed){e->id,e->parent,x->names,e->kind};strcpy(x->base->names+x->names,e->name);}
    x->count++;if(e->parent==e->id)x->roots++;x->names+=strlen(e->name)+1;return true;
}
bool fsearch_catalog_compact_run(FsearchCatalogBuild*t,const char**error) {
    /* Only the builder thread touches replacement/ran/reservation until it is joined.
     * Owner-thread cancellation flags are checked only during publish, avoiding a data race. */
    if(t->ran)return fail(error,"builder_already_ran");
    t->ran=true;
    Collector x={0};fsearch_catalog_view_visit(t->capture,collect,&x);
    Base*b=base_allocate(t->budget,x.count,x.names,x.roots,&t->reservation);
    if(!b)return fail(error,"memory_budget");
    x=(Collector){.base=b};fsearch_catalog_view_visit(t->capture,collect,&x);base_sort(b);t->replacement=b;return true;
}
typedef struct { FsearchCatalogView *candidate; unsigned count; bool equal; } Validation;
static bool validate_entry(const FsearchCatalogEntry*e,void*data) {
    Validation*x=data;FsearchCatalogEntry actual;
    x->count++;
    if(!fsearch_catalog_view_get(x->candidate,e->id,&actual)||actual.parent!=e->parent||actual.kind!=e->kind||strcmp(actual.name,e->name)){x->equal=false;return false;}
    return true;
}
bool fsearch_catalog_compact_validate(FsearchCatalogBuild*t,const char**error) {
    t->validated=false;
    if(!t->replacement)return fail(error,"builder_not_ready");
    FsearchCatalogView candidate={.base=t->replacement};
    Validation x={.candidate=&candidate,.equal=true};
    fsearch_catalog_view_visit(t->capture,validate_entry,&x);
    if(!x.equal||x.count!=t->replacement->count)return fail(error,"validation_failed");
    for(unsigned i=1;i<t->replacement->count;i++) {
        if(!namespace_cmp(&t->replacement->namespace_order[i-1],&t->replacement->namespace_order[i],t->replacement))return fail(error,"validation_failed");
    }
    t->validated=true;return true;
}
void fsearch_catalog_compact_abort(FsearchCatalog*c,FsearchCatalogBuild*t,const char*reason) {
    /* Reason must have static storage duration, like the other error codes. */
    g_mutex_lock(&c->lock);
    if(c->build==t){t->failed=true;t->reason=reason;c->deferred=reason;}
    g_mutex_unlock(&c->lock);
}
bool fsearch_catalog_compact_publish(FsearchCatalog*c,FsearchCatalogBuild*t,const char**error) {
    g_mutex_lock(&c->lock);
    const char*reason=NULL;
    if(c->build!=t)reason="foreign_builder";
    else if(c->closed||t->failed)reason=t->reason?t->reason:"closed";
    else if(t->published)reason="builder_already_published";
    else if(!t->replacement||!t->validated)reason="builder_not_validated";
    else if(g_atomic_int_get(&c->budget->views)>=(int)c->limits.view_limit)reason="reader_budget";
    if(reason){c->deferred=reason;g_mutex_unlock(&c->lock);return fail(error,reason);}
    /* Replay is in acceptance sequence; keep the final mutation for each identity.
     * Replay entries are already validated against the current accepted view. */
    unsigned n=0;
    FsearchCatalogView*next=view_new(c->budget,t->replacement,MIN(t->count,c->limits.overlay_limit),&t->reservation);
    if(!next){c->deferred="memory_budget";g_mutex_unlock(&c->lock);return fail(error,c->deferred);}
    for(unsigned i=0;i<t->count;i++) {
        Delta*d=t->replay[i];unsigned at=0;while(at<n&&next->delta[at]->id<d->id)at++;
        if(at<n&&next->delta[at]->id==d->id){delta_unref(next->delta[at]);next->delta[at]=delta_ref(d);}
        else {
            if(n==c->limits.overlay_limit){next->count=n;fsearch_catalog_view_unref(next);c->deferred="overlay_budget";g_mutex_unlock(&c->lock);return fail(error,c->deferred);}
            memmove(next->delta+at+1,next->delta+at,(n-at)*sizeof(Delta*));next->delta[at]=delta_ref(d);n++;
        }
    }
    next->count=n;next->sequence=c->current->sequence;next->generation=c->current->generation+1;
    FsearchCatalogView*previous=c->current;c->current=next;c->deferred=NULL;t->published=true;
    fsearch_catalog_view_unref(previous);g_mutex_unlock(&c->lock);return true;
}
void fsearch_catalog_compact_free(FsearchCatalog*c,FsearchCatalogBuild*t) {
    if(!t)return;
    g_mutex_lock(&c->lock);g_assert(c->build==t);c->build=NULL;g_mutex_unlock(&c->lock);
    for(unsigned i=0;i<t->count;i++)delta_unref(t->replay[i]);
    if(t->replacement)base_unref(t->replacement);
    fsearch_catalog_view_unref(t->capture);unreserve(t);release(t);
}

/* Streaming native candidate/overlay merge. The only result-sized allocation is
 * the bounded response buffer; matching hits are never collected in a full array. */
static int delta_name_cmp(const void*a,const void*b) {
    Delta*x=*(Delta**)a,*y=*(Delta**)b;
    if(x->kind!=y->kind)return(x->kind>y->kind)-(x->kind<y->kind);
    return fsearch_file_utils_cmp_paths(x->name,y->name);
}
typedef struct {
    FsearchCatalogView *view;
    unsigned next_block, first, end;
    uint64_t possible, required[3];
    bool filter;
    FsearchCatalogQueryResult *result;
    gint64 deadline;
} CandidateCursor;
static bool next_candidate(CandidateCursor*c,FsearchCatalogEntry*e) {
    Base*b=c->view->base;
    for(;;) {
        while(!c->possible) {
            if((c->result->candidate_blocks%64)==0&&g_get_monotonic_time()>=c->deadline){c->result->stop="deadline";return false;}
            unsigned block=c->next_block++;
            if((uint64_t)block*64>=c->end)return false;
            if(++c->result->candidate_blocks>CANDIDATE_BLOCK_BUDGET){c->result->stop="work_limit";return false;}
            uint64_t possible=UINT64_MAX;
            if(c->filter&&b->signatures)for(unsigned w=0;w<3&&possible;w++)for(uint64_t bits=c->required[w];bits&&possible;bits&=bits-1){unsigned bit=__builtin_ctzll(bits);possible&=b->signatures[(w*64+bit)*b->signature_stride+block];}
            c->possible=possible;
        }
        unsigned rank=(c->next_block-1)*64+__builtin_ctzll(c->possible);c->possible&=c->possible-1;
        if(rank<c->first||rank>=c->end)continue;
        Packed*r=&b->entries[b->name_order[rank]];unsigned d=delta_position(c->view,r->id);
        if(d<c->view->count&&c->view->delta[d]->id==r->id)continue;
        *e=(FsearchCatalogEntry){r->id,r->parent,r->kind,b->names+r->offset};return true;
    }
}
static char *bounded_path(FsearchCatalogView*v,uint32_t id,size_t maximum) {
    uint32_t original=id;FsearchCatalogEntry e;size_t length=0;
    for(unsigned depth=0;depth<MAX_DEPTH;depth++) {
        if(!raw_get(v,id,&e)||!e.kind)return NULL;
        size_t n=strlen(e.name);if(n>maximum||length>maximum-n)return NULL;length+=n;
        if(e.parent==e.id)return fsearch_catalog_view_path(v,original);
        if(length==maximum)return NULL;
        length++;id=e.parent;
    }
    return NULL;
}
/* A slash-free raw ASCII literal cannot span a path separator. Memoize
 * current parent visibility/matching by stable identity; no root probes occur. */
static unsigned parent_match(FsearchCatalogView*v,uint32_t id,const Options*o,unsigned char*cache,size_t count) {
    if(strchr(o->query,'/')) {
        if(id<count&&cache[id])return cache[id];
        FsearchCatalogEntry live;
        unsigned result=3;
        if(fsearch_catalog_view_get(v,id,&live)) {
            g_autofree char *path=bounded_path(v,id,4096);
            /* An overlong path remains a candidate: this prefilter must never
             * reject an uncertain match. The authoritative matcher is bounded. */
            result=!path||(o->match_case?strstr(path,o->query):strcasestr(path,o->query))?2:1;
        }
        if(id<count)cache[id]=result;
        return result;
    }
    uint32_t pending[MAX_DEPTH];unsigned n=0,result=1;
    for(;;) {
        if(id<count&&cache[id]){result=cache[id];break;}
        FsearchCatalogEntry e;
        if(n==MAX_DEPTH||!raw_get(v,id,&e)||e.kind!=FSEARCH_CATALOG_FOLDER){result=3;break;}
        pending[n++]=id;
        if(o->match_case?strstr(e.name,o->query)!=NULL:strcasestr(e.name,o->query)!=NULL){
            /* Even a matching folder is invisible if an ancestor was deleted. */
            FsearchCatalogEntry live;result=fsearch_catalog_view_get(v,id,&live)?2:3;break;
        }
        if(e.parent==e.id){result=1;break;}id=e.parent;
    }
    while(n){uint32_t key=pending[--n];if(key<count)cache[key]=result;}
    return result;
}
static bool exact_path_contains(const Options*o,const char*path) {
    bool raw=signature_ascii(o->query)&&(o->match_case||fsearch_string_is_ascii_icase(o->query));
    if(raw)return (o->match_case?strstr(path,o->query):strcasestr(path,o->query))!=NULL;
    g_autoptr(FsearchQuery)q=fsearch_query_new_literal(o->query,o->match_case?QUERY_FLAG_MATCH_CASE:0);
    FsearchQueryMatchData*m=fsearch_query_match_data_new(NULL,NULL);
    FsearchDatabaseEntry*entry=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,path,NULL,DATABASE_ENTRY_TYPE_FOLDER);
    fsearch_query_match_data_set_entry(m,entry);bool result=fsearch_query_match(q,m);
    fsearch_query_match_data_free(m);db_entry_free(entry);return result;
}
/* A path match either ends inside an entry's own name or in an ancestor.
 * Probe folder names with the final component's signature first. If no visible
 * folder path can contain the full literal, the same tail signature is a sound
 * global candidate filter. Uncertainty or the bounded probe cap means fallback. */
static bool ancestor_possible(FsearchCatalogView*v,const Options*o,const char*tail,
                              unsigned first,FsearchCatalogQueryResult*r,gint64 deadline) {
    if(!*tail)return true;
    Options full_options=*o;full_options.path=false;uint64_t full_signature[3];
    if(!query_signature(&full_options,full_signature))return true;
    bool raw=signature_ascii(o->query)&&(o->match_case||fsearch_string_is_ascii_icase(o->query));
    Options name_options=*o;name_options.path=false;name_options.query=(char*)tail;
    CandidateCursor folders={.view=v,.first=first,.next_block=first/64,.end=v->base->count,.result=r,.deadline=deadline};
    folders.filter=query_signature(&name_options,folders.required);
    unsigned probes=0;FsearchCatalogEntry e;
    for(unsigned phase=0;phase<2;phase++) {
        unsigned d=0;
        for(;;) {
            if(!phase){if(!next_candidate(&folders,&e))break;}
            else {
                if(d==v->count)break;
                Delta*x=v->delta[d++];if(x->kind!=FSEARCH_CATALOG_FOLDER)continue;
                e=(FsearchCatalogEntry){x->id,x->parent,x->kind,x->name};
            }
            if(raw&&!(o->match_case?strstr(e.name,tail):strcasestr(e.name,tail)))continue;
            if(++probes>4096||g_get_monotonic_time()>=deadline)return true;
            FsearchCatalogEntry live;if(!fsearch_catalog_view_get(v,e.id,&live))continue;
            g_autofree char *path=bounded_path(v,e.id,4096);
            if(!path||exact_path_contains(o,path))return true;
        }
    }
    return strcmp(r->stop,"ok")!=0;
}
void fsearch_catalog_query_clear(FsearchCatalogQueryResult*r){if(r->rows)g_string_free(r->rows,true);memset(r,0,sizeof(*r));}
bool fsearch_catalog_query(FsearchCatalogView*v,const Options*o,FsearchCatalogQueryResult*r,const char**error) {
    memset(r,0,sizeof(*r));r->stop="ok";
    if(!v||!o||!o->query||!g_utf8_validate(o->query,-1,NULL)||strlen(o->query)>4096||!o->kind
       ||(strcmp(o->kind,"all")&&strcmp(o->kind,"files")&&strcmp(o->kind,"folders"))
       ||o->limit<1||o->limit>1000||o->max_candidates<1||o->max_candidates>MAX_CANDIDATES
       ||o->max_bytes<512||o->max_bytes>MAX_RESPONSE_BYTES
       ||(o->extension&&(!g_utf8_validate(o->extension,-1,NULL)||strlen(o->extension)>512)))return fail(error,"invalid_query");
    Delta**delta=g_try_malloc_n(MAX(v->count,1u),sizeof(Delta*));if(!delta)return fail(error,"memory_budget");
    unsigned delta_count=0;
    for(unsigned i=0;i<v->count;i++){Delta*d=v->delta[i];if(d->kind&&(!strcmp(o->kind,"all")||d->kind==(!strcmp(o->kind,"files")?1u:2u)))delta[delta_count++]=d;}
    qsort(delta,delta_count,sizeof(Delta*),delta_name_cmp);
    gint64 started=g_get_monotonic_time();gint64 deadline=started+(o->timeout_ms>0?(gint64)o->timeout_ms*1000:G_MAXINT64-started);
    CandidateCursor cursor={.view=v,.end=v->base->count,.result=r,.deadline=deadline};cursor.filter=query_signature(o,cursor.required);
    /* The sorted base is files then folders. Skip the irrelevant kind in O(log N). */
    unsigned lo=0,hi=v->base->count;
    while(lo<hi){unsigned m=lo+(hi-lo)/2;if(v->base->entries[v->base->name_order[m]].kind==FSEARCH_CATALOG_FILE)lo=m+1;else hi=m;}
    const char *tail=strrchr(o->query,'/');tail=tail?tail+1:o->query;
    bool path_parts=o->path&&*o->query&&signature_ascii(o->query)&&(o->match_case||fsearch_string_is_ascii_icase(o->query));
    if(o->path&&*o->query&&!ancestor_possible(v,o,tail,lo,r,deadline)) {
        Options name_options=*o;name_options.path=false;name_options.query=(char*)tail;
        cursor.filter=query_signature(&name_options,cursor.required);
    }
    if(!strcmp(o->kind,"folders")){cursor.first=lo;cursor.next_block=lo/64;}
    if(!strcmp(o->kind,"files"))cursor.end=lo;
    FsearchCatalogEntry base_entry;bool has_base=next_candidate(&cursor,&base_entry);unsigned d=0;
    g_autoptr(FsearchQuery)q=fsearch_query_new_literal(o->query,(o->path?QUERY_FLAG_SEARCH_IN_PATH:0)|(o->match_case?QUERY_FLAG_MATCH_CASE:0));
    FsearchQueryMatchData*m=fsearch_query_match_data_new(NULL,NULL);r->rows=g_string_sized_new(MIN(o->max_bytes/2,4096));
    size_t parent_count=path_parts?MIN((uint64_t)v->base->entries[v->base->count-1].id+1,16UL*1024*1024):0;
    unsigned char*parents=path_parts?g_try_malloc0(parent_count):NULL;
    if(path_parts&&!parents){fsearch_catalog_query_clear(r);fsearch_query_match_data_free(m);g_free(delta);return fail(error,"memory_budget");}
    /* If a slash-containing literal reaches the basename, its final component
     * must occur in that basename. Otherwise the full literal lies in the parent
     * path. A trailing slash has an empty tail and admits every basename. */
    bool ascii_query=!o->path&&signature_ascii(o->query),raw_ascii=ascii_query&&(o->match_case||fsearch_string_is_ascii_icase(o->query));
    while((has_base||d<delta_count)&&!strcmp(r->stop,"ok")) {
        if(g_get_monotonic_time()>=deadline){r->stop="deadline";break;}
        FsearchCatalogEntry e;
        bool use_base=d==delta_count||(has_base&&(base_entry.kind<delta[d]->kind||(base_entry.kind==delta[d]->kind&&fsearch_file_utils_cmp_paths(base_entry.name,delta[d]->name)<=0)));
        if(use_base){e=base_entry;has_base=next_candidate(&cursor,&base_entry);}
        else {Delta*x=delta[d++];e=(FsearchCatalogEntry){x->id,x->parent,x->kind,x->name};}
        if(path_parts) {
            unsigned possible=parent_match(v,e.parent,o,parents,parent_count);
            if(possible==3)continue;
            if(possible==1&&!(o->match_case?strstr(e.name,tail):strcasestr(e.name,tail)))continue;
        }
        FsearchCatalogEntry live;if(!fsearch_catalog_view_get(v,e.id,&live))continue;
        if(ascii_query&&(raw_ascii||signature_ascii(e.name))) {
            bool match=o->match_case?strstr(e.name,o->query)!=NULL:strlen(o->query)>0&&strlen(o->query)<3?short_ascii_contains(e.name,o->query,false):strcasestr(e.name,o->query)!=NULL;
            if(!match)continue;
        }
        if(r->examined>=(unsigned)o->max_candidates){r->stop="work_limit";break;}r->examined++;
        FsearchDatabaseEntry*parent=NULL,*entry=NULL;
        if(o->path&&e.parent!=e.id){g_autofree char*p=bounded_path(v,e.parent,o->max_bytes/2);if(!p){r->stop="byte_limit";break;}parent=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,p,NULL,DATABASE_ENTRY_TYPE_FOLDER);}
        entry=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,e.name,parent,e.kind==FSEARCH_CATALOG_FILE?DATABASE_ENTRY_TYPE_FILE:DATABASE_ENTRY_TYPE_FOLDER);
        const char*ext=db_entry_get_extension(entry);
        bool match=!o->extension||(e.kind==FSEARCH_CATALOG_FILE&&ext&&!g_ascii_strcasecmp(ext,o->extension));
        if(match){fsearch_query_match_data_set_entry(m,entry);match=fsearch_query_match(q,m);}
        db_entry_free(entry);if(parent)db_entry_free(parent);
        if(!match)continue;
        if(r->returned>=(unsigned)o->limit){r->stop="result_limit";break;}
        g_autofree char*path=bounded_path(v,e.id,o->max_bytes/2);if(!path){r->stop="byte_limit";break;}
        g_autoptr(GString)row=g_string_new("{\"path\":");
        if(g_utf8_validate(path,-1,NULL)){fsearch_headless_append_json_string(row,path);g_string_append(row,",\"path_bytes_base64\":null}");}
        else{g_autofree char*encoded=g_base64_encode((guchar*)path,strlen(path));g_string_append(row,"null,\"path_bytes_base64\":");fsearch_headless_append_json_string(row,encoded);g_string_append_c(row,'}');}
        if(r->rows->len+row->len+1>(unsigned)o->max_bytes/2){r->stop="byte_limit";break;}
        if(r->returned)g_string_append_c(r->rows,',');
        g_string_append_len(r->rows,row->str,row->len);r->returned++;
    }
    fsearch_query_match_data_free(m);g_free(parents);g_free(delta);return true;
}

static bool child(FsearchCatalogView*v,uint32_t parent,const char*name,FsearchCatalogEntry*out) {
    for(unsigned i=0;i<v->count;i++){Delta*d=v->delta[i];if(d->kind&&d->parent==parent&&!strcmp(d->name,name))return fsearch_catalog_view_get(v,d->id,out);}
    Base*b=v->base;unsigned lo=0,hi=b->count;
    while(lo<hi){unsigned m=lo+(hi-lo)/2;Packed*r=&b->entries[b->namespace_order[m]];int cmp=r->parent==parent?strcmp(b->names+r->offset,name):(r->parent>parent?1:-1);if(cmp<0)lo=m+1;else hi=m;}
    if(lo==b->count)return false;Packed*r=&b->entries[b->namespace_order[lo]];
    if(r->parent!=parent||strcmp(b->names+r->offset,name))return false;
    unsigned at=delta_position(v,r->id);if(at<v->count&&v->delta[at]->id==r->id)return false;
    return fsearch_catalog_view_get(v,r->id,out);
}
bool fsearch_catalog_view_lookup(FsearchCatalogView*v,const char*path,FsearchCatalogEntry*out) {
    if(!v||!path||path[0]!='/'||strnlen(path,MAX_NAME+1)>MAX_NAME)return false;
    Base*b=v->base;size_t longest=0;Packed*root=NULL;bool ambiguous=false;
    for(unsigned i=0;i<b->root_count;i++) {
        Packed*r=&b->entries[b->root_order[i]];const char*name=b->names+r->offset;size_t n=strlen(name);
        if(strncmp(path,name,n)||(n>1&&name[n-1]!='/'&&path[n]&&path[n]!='/'))continue;
        if(n>longest){longest=n;root=r;ambiguous=false;}else if(n==longest)ambiguous=true;
    }
    if(!root||ambiguous)return false;
    if(!fsearch_catalog_view_get(v,root->id,out))return false;
    const char*p=path+longest;char name[MAX_NAME+1];
    while(*p){while(*p=='/')p++;if(!*p)break;const char*end=strchr(p,'/');size_t n=end?(size_t)(end-p):strlen(p);if(!n||n>MAX_NAME)return false;memcpy(name,p,n);name[n]=0;if(!child(v,out->id,name,out))return false;p+=n;}
    return true;
}

/* FSCG0001: fixed network-independent little-endian header and entry frames,
 * followed by SHA256. Streamed cache I/O; no filename resolution or root reads. */
#define CHECKPOINT_MAX_BYTES (512u * 1024u * 1024u)
#define CHECKPOINT_HEADER 76u
typedef struct { int fd; off_t offset; GChecksum *checksum; bool writing; } CheckpointIO;
static bool checkpoint_io(CheckpointIO *io, void *data, size_t size) {
    size_t total=size;unsigned char *p=data;
    if(size>CHECKPOINT_MAX_BYTES || io->offset>CHECKPOINT_MAX_BYTES-size)return false;
    while(size){ssize_t n=io->writing?pwrite(io->fd,p,size,io->offset):pread(io->fd,p,size,io->offset);
        if(n<0&&errno==EINTR)continue;
        if(n<=0)return false;
        io->offset+=n;p+=n;size-=n;
    }
    if(io->checksum)g_checksum_update(io->checksum,data,total);
    return true;
}
static void checkpoint_put32(unsigned char *p,uint32_t value){value=GUINT32_TO_LE(value);memcpy(p,&value,4);}
static void checkpoint_put64(unsigned char *p,uint64_t value){value=GUINT64_TO_LE(value);memcpy(p,&value,8);}
static uint32_t checkpoint_get32(const unsigned char*p){uint32_t v;memcpy(&v,p,4);return GUINT32_FROM_LE(v);}
static uint64_t checkpoint_get64(const unsigned char*p){uint64_t v;memcpy(&v,p,8);return GUINT64_FROM_LE(v);}
static void checkpoint_binding(const char *identity,unsigned char digest[32]) {
    GChecksum *sum=g_checksum_new(G_CHECKSUM_SHA256);g_checksum_update(sum,(const guchar*)identity,strlen(identity));
    gsize n=32;g_checksum_get_digest(sum,digest,&n);g_checksum_free(sum);
}
typedef struct { uint32_t count,roots; uint64_t names; CheckpointIO *io; } CheckpointEntries;
static bool checkpoint_count(const FsearchCatalogEntry *e,void *data) {
    CheckpointEntries *x=data;if(x->count==UINT32_MAX)return false;
    x->count++;x->roots+=e->parent==e->id;x->names+=strlen(e->name)+1;
    return x->names<=UINT32_MAX;
}
static bool checkpoint_entry(const FsearchCatalogEntry *e,void *data) {
    CheckpointEntries *x=data;unsigned char frame[16];uint32_t n=strlen(e->name);
    checkpoint_put32(frame,e->id);checkpoint_put32(frame+4,e->parent);
    checkpoint_put32(frame+8,e->kind);checkpoint_put32(frame+12,n);
    return checkpoint_io(x->io,frame,sizeof(frame))&&checkpoint_io(x->io,(void*)e->name,n);
}
struct FsearchCatalogCheckpoint { FsearchCatalogView *view; uint32_t highwater; off_t bytes; unsigned char digest[32]; bool written; };
FsearchCatalogCheckpoint *fsearch_catalog_checkpoint_capture(FsearchCatalog *c,const char **error) {
    g_mutex_lock(&c->lock);
    FsearchCatalogCheckpoint *capture=c->closed?NULL:allocate(c->budget,sizeof(*capture),NULL);
    if(capture){capture->view=fsearch_catalog_view_ref(c->current);capture->highwater=c->highwater;}
    bool closed=c->closed;g_mutex_unlock(&c->lock);
    if(!capture)fail(error,closed?"closed":"memory_budget");
    return capture;
}
void fsearch_catalog_checkpoint_free(FsearchCatalogCheckpoint *capture) {
    if(capture){fsearch_catalog_view_unref(capture->view);release(capture);}
}
uint64_t fsearch_catalog_checkpoint_sequence(FsearchCatalogCheckpoint *capture){return capture->view->sequence;}
bool fsearch_catalog_checkpoint_write(FsearchCatalog *c,int fd,const char *identity,const char **error) {
    FsearchCatalogCheckpoint *capture=fsearch_catalog_checkpoint_capture(c,error);if(!capture)return false;
    bool ok=fsearch_catalog_checkpoint_write_capture(capture,fd,identity,error);
    fsearch_catalog_checkpoint_free(capture);return ok;
}
bool fsearch_catalog_checkpoint_write_capture(FsearchCatalogCheckpoint *capture,int fd,const char *identity,const char **error) {
    struct stat st;
    if(!capture||!identity||!*identity||fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size)return fail(error,"checkpoint_output");
    FsearchCatalogView *v=capture->view;uint32_t high=capture->highwater;
    CheckpointEntries entries={0};bool ok=fsearch_catalog_view_visit(v,checkpoint_count,&entries);
    if(!ok||CHECKPOINT_HEADER+entries.names+(uint64_t)entries.count*15+32>CHECKPOINT_MAX_BYTES){return fail(error,"checkpoint_budget");}
    unsigned char header[CHECKPOINT_HEADER]={0};memcpy(header,"FSCG0001",8);
    checkpoint_put64(header+8,v->sequence);checkpoint_put64(header+16,v->generation);
    checkpoint_put32(header+24,high);checkpoint_put32(header+28,entries.count);
    checkpoint_put64(header+32,entries.names);checkpoint_put32(header+40,entries.roots);checkpoint_binding(identity,header+44);
    CheckpointIO io={fd,0,g_checksum_new(G_CHECKSUM_SHA256),true};entries.io=&io;
    ok=checkpoint_io(&io,header,sizeof(header))&&fsearch_catalog_view_visit(v,checkpoint_entry,&entries);
    unsigned char digest[32];gsize n=sizeof(digest);g_checksum_get_digest(io.checksum,digest,&n);g_checksum_free(io.checksum);io.checksum=NULL;
    ok=ok&&checkpoint_io(&io,digest,sizeof(digest))&&fsync(fd)==0;
    capture->written=ok;
    if(ok){capture->bytes=io.offset;memcpy(capture->digest,digest,32);}
    return ok||fail(error,"checkpoint_write_failed");
}
bool fsearch_catalog_checkpoint_verify_capture(FsearchCatalogCheckpoint *capture,int fd,const char **error) {
    struct stat st;
    if(!capture||!capture->written||fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size!=capture->bytes)return fail(error,"checkpoint_readback_failed");
    CheckpointIO io={fd,0,g_checksum_new(G_CHECKSUM_SHA256),false};unsigned char buffer[65536];bool ok=true;
    while(io.offset<capture->bytes-32&&ok){size_t n=MIN((off_t)sizeof(buffer),capture->bytes-32-io.offset);ok=checkpoint_io(&io,buffer,n);}
    unsigned char digest[32],footer[32];gsize n=32;g_checksum_get_digest(io.checksum,digest,&n);g_checksum_free(io.checksum);io.checksum=NULL;
    ok=ok&&!memcmp(digest,capture->digest,32)&&checkpoint_io(&io,footer,32)&&!memcmp(footer,capture->digest,32);
    return ok||fail(error,"checkpoint_readback_failed");
}
FsearchCatalog *fsearch_catalog_checkpoint_read(int fd,const char *identity,const FsearchCatalogLimits *limits,const char **error) {
    struct stat st;unsigned char header[CHECKPOINT_HEADER],binding[32];
    if(!identity||!*identity||!limits||!limits->memory_limit||!limits->overlay_limit||!limits->replay_limit
       ||limits->overlay_limit>65536||limits->replay_limit>65536||limits->view_limit<3||limits->view_limit>64
       ||fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size<CHECKPOINT_HEADER+32||st.st_size>CHECKPOINT_MAX_BYTES){fail(error,"checkpoint_invalid");return NULL;}
    CheckpointIO io={fd,0,g_checksum_new(G_CHECKSUM_SHA256),false};
    if(!checkpoint_io(&io,header,sizeof(header))||memcmp(header,"FSCG0001",8)){g_checksum_free(io.checksum);fail(error,"checkpoint_invalid");return NULL;}
    checkpoint_binding(identity,binding);
    if(memcmp(binding,header+44,32)){g_checksum_free(io.checksum);fail(error,"checkpoint_binding");return NULL;}
    unsigned count=checkpoint_get32(header+28),roots=checkpoint_get32(header+40);uint64_t names=checkpoint_get64(header+32);
    if(!count||!roots||roots>count||names<count||names>UINT32_MAX
       ||CHECKPOINT_HEADER+names+(uint64_t)count*15+32!=(uint64_t)st.st_size){g_checksum_free(io.checksum);fail(error,"checkpoint_invalid");return NULL;}
    Budget *b=calloc(1,sizeof(*b));if(!b){g_checksum_free(io.checksum);fail(error,"allocation_failed");return NULL;}
    b->refs=1;b->limit=limits->memory_limit;g_mutex_init(&b->lock);
    FsearchCatalog *c=allocate(b,sizeof(*c),NULL);Base *base=base_allocate(b,count,names,roots,NULL);
    if(!c||!base){release(c);if(base)base_unref(base);budget_unref(b);g_checksum_free(io.checksum);fail(error,"memory_budget");return NULL;}
    c->budget=b;c->limits=*limits;c->highwater=checkpoint_get32(header+24);g_mutex_init(&c->lock);
    size_t offset=0;unsigned seen_roots=0;bool ok=true;
    for(unsigned i=0;i<count&&ok;i++) {
        unsigned char frame[16];ok=checkpoint_io(&io,frame,sizeof(frame));if(!ok)break;
        uint32_t id=checkpoint_get32(frame),parent=checkpoint_get32(frame+4),kind=checkpoint_get32(frame+8),n=checkpoint_get32(frame+12);
        if(!n||n>MAX_NAME||n+1>names-offset||id>c->highwater||kind<FSEARCH_CATALOG_FILE||kind>FSEARCH_CATALOG_FOLDER){ok=false;break;}
        char *name=base->names+offset;ok=checkpoint_io(&io,name,n);if(!ok||memchr(name,0,n)){ok=false;break;}name[n]=0;
        if((parent!=id&&!basename_valid(name))||(parent==id&&(kind!=FSEARCH_CATALOG_FOLDER||name[0]!='/'))){ok=false;break;}
        base->entries[i]=(Packed){id,parent,offset,kind};offset+=n+1;seen_roots+=parent==id;
    }
    unsigned char actual[32],expected[32];gsize digest_size=32;
    g_checksum_get_digest(io.checksum,expected,&digest_size);g_checksum_free(io.checksum);io.checksum=NULL;
    ok=ok&&offset==names&&seen_roots==roots&&checkpoint_io(&io,actual,sizeof(actual))
       &&io.offset==st.st_size&&!memcmp(actual,expected,32);
    if(ok){base_sort(base);c->current=view_new(b,base,0,NULL);ok=c->current!=NULL;}
    base_unref(base);
    if(ok){c->current->sequence=checkpoint_get64(header+8);c->current->generation=checkpoint_get64(header+16);
        Base *x=c->current->base;ok=x->entries[0].id==0&&x->entries[0].parent==0;
        for(unsigned i=0;i<count&&ok;i++){FsearchCatalogEntry entry;Packed*r=&x->entries[i];
            ok=(!i||r->id!=x->entries[i-1].id)&&fsearch_catalog_view_get(c->current,r->id,&entry);
        }
        for(unsigned i=1;i<count&&ok;i++)ok=namespace_cmp(&x->namespace_order[i-1],&x->namespace_order[i],x)!=0;
    }
    if(!ok){fsearch_catalog_free(c);fail(error,"checkpoint_invalid");return NULL;}
    return c;
}
