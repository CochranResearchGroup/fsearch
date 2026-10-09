/* Immutable base + bounded copy-on-write overlay, with explicit compaction replay.
 * No filesystem operations. GLib locks protect ownership, not indexed storage.
 * GPL-2.0-or-later. */
#include "fsearch_catalog.h"
#include <stdlib.h>
#include <string.h>
#include <stdalign.h>

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
    uint32_t *namespace_order;
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
        if(!e.id)return e.kind==FSEARCH_CATALOG_FOLDER;
        if(!raw_get(v,e.parent,&e)||e.kind!=FSEARCH_CATALOG_FOLDER)return false;
    }
    return false;
}
char *fsearch_catalog_view_path(FsearchCatalogView*v,uint32_t id) {
    FsearchCatalogEntry e;if(!fsearch_catalog_view_get(v,id,&e))return NULL;
    const char*names[MAX_DEPTH];unsigned n=0;
    for(;;){if(n==MAX_DEPTH)return NULL;names[n++]=e.name;if(!e.id)break;if(!raw_get(v,e.parent,&e))return NULL;}
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
static Base *base_allocate(Budget*b,unsigned n,size_t names,size_t*reservation) {
    if(names>UINT32_MAX||n>(SIZE_MAX-sizeof(Base)-names)/(sizeof(Packed)+sizeof(uint32_t)))return NULL;
    Base*x=allocate(b,sizeof(*x)+(size_t)n*(sizeof(Packed)+sizeof(uint32_t))+names,reservation);
    if(!x)return NULL;
    x->refs=1;x->count=n;x->names_size=names;x->entries=(Packed*)(x+1);
    x->namespace_order=(uint32_t*)(x->entries+n);x->names=(char*)(x->namespace_order+n);return x;
}
static void base_sort(Base*b) {
    qsort(b->entries,b->count,sizeof(Packed),packed_id);
    for(unsigned i=0;i<b->count;i++)b->namespace_order[i]=i;
    g_qsort_with_data(b->namespace_order,b->count,sizeof(uint32_t),namespace_cmp,b);
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
    if(!entries||!count||!limits||!limits->memory_limit||!limits->overlay_limit||!limits->replay_limit||limits->view_limit<3){fail(error,"invalid_limits");return NULL;}
    size_t names=0;uint32_t high=0;
    for(unsigned i=0;i<count;i++){
        const FsearchCatalogEntry*e=&entries[i];size_t n=e->name?strnlen(e->name,MAX_NAME+1):MAX_NAME+1;
        if(n>MAX_NAME||!n||e->kind<FSEARCH_CATALOG_FILE||e->kind>FSEARCH_CATALOG_FOLDER
           ||(e->id&&!basename_valid(e->name))||(!e->id&&(e->kind!=FSEARCH_CATALOG_FOLDER||e->parent||e->name[0]!='/'))){fail(error,"invalid_entry");return NULL;}
        names+=n+1;high=MAX(high,e->id);
    }
    Budget*b=calloc(1,sizeof(*b));if(!b){fail(error,"allocation_failed");return NULL;}b->refs=1;b->limit=limits->memory_limit;g_mutex_init(&b->lock);
    FsearchCatalog*c=allocate(b,sizeof(*c),NULL);Base*base=base_allocate(b,count,names,NULL);
    if(!c||!base){release(c);if(base)base_unref(base);budget_unref(b);fail(error,"memory_budget");return NULL;}
    c->budget=b;c->limits=*limits;c->highwater=high;g_mutex_init(&c->lock);
    size_t offset=0;for(unsigned i=0;i<count;i++){const FsearchCatalogEntry*e=&entries[i];base->entries[i]=(Packed){e->id,e->parent,offset,e->kind};strcpy(base->names+offset,e->name);offset+=strlen(e->name)+1;}
    base_sort(base);c->current=view_new(b,base,0,NULL);base_unref(base);
    if(!c->current){fsearch_catalog_free(c);fail(error,"memory_budget");return NULL;}
    bool valid=c->current->base->entries[0].id==0;
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
    if(!create&&(!id||!fsearch_catalog_view_get(v,id,&old)))return fail(error,"retired_identity");
    if(kind>FSEARCH_CATALOG_FOLDER||kind<FSEARCH_CATALOG_DELETED)return fail(error,"invalid_kind");
    if(kind) {
        if(!basename_valid(name)||!fsearch_catalog_view_get(v,parent,&p)||p.kind!=FSEARCH_CATALOG_FOLDER)return fail(error,"invalid_parent_or_name");
        if(!create&&old.kind!=kind)return fail(error,"type_transition_requires_new_identity");
        unsigned depth=0;for(;;){if(p.id==id)return fail(error,"cycle");if(!p.id)break;if(++depth>=MAX_DEPTH-1)return fail(error,"depth_limit");if(!raw_get(v,p.parent,&p))return fail(error,"invalid_parent");}
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
    size_t needed=cost(sizeof(Base)+count*(sizeof(Packed)+sizeof(uint32_t))+names)
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
typedef struct { unsigned count;size_t names;Base*base; } Collector;
static bool collect(const FsearchCatalogEntry*e,void*data) {
    Collector*x=data;
    if(x->base){x->base->entries[x->count]=(Packed){e->id,e->parent,x->names,e->kind};strcpy(x->base->names+x->names,e->name);}
    x->count++;x->names+=strlen(e->name)+1;return true;
}
bool fsearch_catalog_compact_run(FsearchCatalogBuild*t,const char**error) {
    /* Only the builder thread touches replacement/ran/reservation until it is joined.
     * Owner-thread cancellation flags are checked only during publish, avoiding a data race. */
    if(t->ran)return fail(error,"builder_already_ran");
    t->ran=true;
    Collector x={0};fsearch_catalog_view_visit(t->capture,collect,&x);
    Base*b=base_allocate(t->budget,x.count,x.names,&t->reservation);
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
