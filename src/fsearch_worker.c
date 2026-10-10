/* Resident query worker. Private supervised binary protocol. GPL-2.0-or-later. */
#include "fsearch_headless.h"
#include "fsearch_catalog.h"
#include <arpa/inet.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>

static bool read_all(void *buffer, size_t size) {
    char *p = buffer;
    while (size) { ssize_t n = read(STDIN_FILENO, p, size); if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return false;
        p += n; size -= n; }
    return true;
}
static bool write_all(const void *buffer, size_t size) {
    const char *p = buffer;
    while (size) { ssize_t n = write(STDOUT_FILENO, p, size); if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return false;
        p += n; size -= n; }
    return true;
}
static bool send_frame(const char *body, size_t size) {
    uint32_t length = htonl(size);
    return write_all(&length, sizeof(length)) && write_all(body, size);
}
static void discard_log(const gchar *domain, GLogLevelFlags level, const gchar *message, gpointer data) {
    (void)domain; (void)level; (void)message; (void)data;
}
typedef struct {
    FsearchHeadlessSnapshot *snapshot;
    FsearchCatalogBuild *build;
    GThread *thread;
    gint done;
    bool valid;
    const char *error;
    FsearchCatalogCheckpoint *checkpoint;
    GThread *checkpoint_thread;
    gint checkpoint_done;
    bool checkpoint_valid, checkpoint_seen;
    const char *checkpoint_error;
    int checkpoint_fd, checkpoint_metadata_fd;
    char *checkpoint_path;
    uint64_t checkpoint_sequence;
} CatalogWorker;
static gpointer checkpoint_thread(void *data) {
    CatalogWorker *w=data;
    w->checkpoint_valid=fsearch_catalog_checkpoint_write_capture(w->checkpoint,w->checkpoint_fd,
                            fsearch_headless_identity(w->snapshot),&w->checkpoint_error);
    if(w->checkpoint_valid)w->checkpoint_valid=fsearch_headless_checkpoint_metadata_write(w->snapshot,w->checkpoint_metadata_fd,w->checkpoint_sequence,&w->checkpoint_error);
    if(w->checkpoint_valid)w->checkpoint_valid=fsearch_catalog_checkpoint_verify_capture(w->checkpoint,w->checkpoint_fd,&w->checkpoint_error);
    close(w->checkpoint_metadata_fd);
    close(w->checkpoint_fd);g_atomic_int_set(&w->checkpoint_done,1);return NULL;
}
static void checkpoint_poll(CatalogWorker *w) {
    if(!w->checkpoint_thread||!g_atomic_int_get(&w->checkpoint_done))return;
    g_thread_join(w->checkpoint_thread);w->checkpoint_thread=NULL;
    fsearch_catalog_checkpoint_free(w->checkpoint);w->checkpoint=NULL;
}
static gpointer compact_thread(void*data) {
    CatalogWorker*w=data;
    w->valid=fsearch_catalog_compact_run(w->build,&w->error)&&fsearch_catalog_compact_validate(w->build,&w->error);
    g_atomic_int_set(&w->done,1);return NULL;
}
static void compact_poll(CatalogWorker*w) {
    if(!w->thread||!g_atomic_int_get(&w->done))return;
    g_thread_join(w->thread);w->thread=NULL;
    FsearchCatalog*c=fsearch_headless_catalog(w->snapshot);
    if(w->valid)fsearch_catalog_compact_publish(c,w->build,&w->error);
    else fsearch_catalog_compact_abort(c,w->build,w->error?w->error:"builder_failed");
    fsearch_catalog_compact_free(c,w->build);w->build=NULL;
}
static void catalog_cleanup(CatalogWorker*w) {
    if(w->checkpoint_thread){g_thread_join(w->checkpoint_thread);w->checkpoint_thread=NULL;fsearch_catalog_checkpoint_free(w->checkpoint);w->checkpoint=NULL;}
    g_free(w->checkpoint_path);w->checkpoint_path=NULL;
    if(!w->thread)return;
    FsearchCatalog*c=fsearch_headless_catalog(w->snapshot);fsearch_catalog_close(c);
    g_thread_join(w->thread);w->thread=NULL;fsearch_catalog_compact_free(c,w->build);w->build=NULL;
}
static bool catalog_command(CatalogWorker*w,const uint32_t wire[7]) {
    FsearchCatalog*c=fsearch_headless_catalog(w->snapshot);uint32_t op=wire[0];
    if(op<0x100||op>0x107||wire[6]>4096)return false;
    char name[4097]={0};if(!read_all(name,wire[6])||strlen(name)!=wire[6])return false;
    const char*error=NULL;const char*status="catalog_status";uint32_t id=wire[3],parent=wire[2],kind=wire[1];
    FsearchCatalogEntry entry={0};bool located=false;
    if(!c)error="catalog_unavailable";
    else if(op==0x100||op==0x101) {
        if(kind>2||(kind&&(!wire[6]))||(op==0x100&&(!kind||id)))return false;
        uint64_t sequence=((uint64_t)wire[4]<<32)|wire[5];
        bool ok=op==0x100?fsearch_catalog_create(c,sequence,parent,kind,name,&id,&error):fsearch_catalog_change(c,sequence,id,parent,kind,name,&error);
        status=ok?"catalog_applied":"error";
    } else if(op==0x105||op==0x106) {
        if(wire[1]||wire[2]||wire[3]||wire[4]||wire[5]||!wire[6]||name[0]!='/')return false;
        if(w->build||w->checkpoint_thread)error="builder_busy";
        else {
            int flags=op==0x105?O_RDWR|O_CREAT|O_EXCL:O_RDONLY;
            int fd=open(name,flags|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK,0600);struct stat info;
            if(fd<0)error="checkpoint_open_failed";
            else {
                if(fstat(fd,&info)||!S_ISREG(info.st_mode)||info.st_uid!=geteuid()||(info.st_mode&077)||info.st_nlink!=1)error="checkpoint_custody";
                else if(op==0x105) {
                    w->checkpoint=fsearch_catalog_checkpoint_capture(c,&error);
                    if(w->checkpoint){
                        g_autofree char *metadata_name=g_strconcat(name,".metadata",NULL);
                        int metadata_fd=open(metadata_name,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
                        if(metadata_fd<0){fsearch_catalog_checkpoint_free(w->checkpoint);w->checkpoint=NULL;error="checkpoint_metadata_output";}
                        else {w->checkpoint_fd=fd;fd=-1;w->checkpoint_metadata_fd=metadata_fd;
                            g_free(w->checkpoint_path);w->checkpoint_path=g_strdup(name);
                            w->checkpoint_sequence=fsearch_catalog_checkpoint_sequence(w->checkpoint);
                            w->checkpoint_error=NULL;w->checkpoint_valid=false;w->checkpoint_seen=true;g_atomic_int_set(&w->checkpoint_done,0);
                            w->checkpoint_thread=g_thread_new("catalog-checkpoint",checkpoint_thread,w);status="catalog_checkpointing";}
                    }
                }
                else if(fsearch_headless_restore_catalog(w->snapshot,fd,&error))status="catalog_restored";
                if(fd>=0)close(fd);
                c=fsearch_headless_catalog(w->snapshot);
            }
        }
    } else if(op==0x107) {
        if(wire[1]||wire[2]||wire[3]||wire[4]||wire[5]||wire[6])return false;
        if(!w->checkpoint_seen)error="checkpoint_missing";
        else if(w->checkpoint_thread)status="catalog_checkpointing";
        else if(w->checkpoint_valid)status="catalog_checkpointed";
        else error=w->checkpoint_error?w->checkpoint_error:"checkpoint_write_failed";
    } else if(op==0x104) {
        if(wire[1]||wire[2]||wire[3]||wire[4]||wire[5]||!wire[6]||name[0]!='/')return false;
        g_autoptr(FsearchCatalogView)v=fsearch_catalog_acquire(c);located=fsearch_catalog_view_lookup(v,name,&entry);status=located?"catalog_located":"catalog_missing";
    } else {
        if(wire[1]||wire[2]||wire[3]||wire[4]||wire[5]||wire[6])return false;
        if(op==0x102) {
            if(w->build)error="builder_busy";
            else {w->build=fsearch_catalog_compact_begin(c,&error);if(w->build){w->error=NULL;w->valid=false;g_atomic_int_set(&w->done,0);w->thread=g_thread_new("catalog-compact",compact_thread,w);status="catalog_compacting";}}
        }
    }
    FsearchCatalogStatus state={0};if(c)fsearch_catalog_status(c,&state);
    GString*out=g_string_new(NULL);g_string_append_printf(out,"{\"schema_version\":1,\"status\":\"%s\",\"complete\":false,\"results\":[],\"durable\":false,\"snapshot_id\":",error?"error":status);
    fsearch_headless_append_json_string(out,fsearch_headless_identity(w->snapshot));
    g_string_append_printf(out,",\"sequence\":%llu,\"generation\":%llu,\"building\":%s,\"deferred_reason\":",(unsigned long long)state.sequence,(unsigned long long)state.generation,state.building?"true":"false");
    if(state.deferred_reason)fsearch_headless_append_json_string(out,state.deferred_reason);else g_string_append(out,"null");
    if(w->checkpoint_seen)g_string_append_printf(out,",\"checkpoint_sequence\":%llu",(unsigned long long)w->checkpoint_sequence);
    if(error){g_string_append(out,",\"error\":{\"code\":");fsearch_headless_append_json_string(out,error);g_string_append_c(out,'}');}
    else if(op==0x100||op==0x101)g_string_append_printf(out,",\"entry_id\":%u",id);
    else if(located)g_string_append_printf(out,",\"entry_id\":%u,\"parent_id\":%u,\"entry_kind\":%u",entry.id,entry.parent,entry.kind);
    g_string_append_c(out,'}');bool sent=send_frame(out->str,out->len);g_string_free(out,true);return sent;
}
int main(int argc, char **argv) {
    if (argc != 3 && (argc != 5 || strcmp(argv[3],"--checkpoint"))) return 2;
    if (prctl(PR_SET_PDEATHSIG, SIGKILL) < 0 || getppid() != (pid_t)atoi(argv[2])) return 2;
    g_log_set_default_handler(discard_log, NULL);
    char gate;
    if (!read_all(&gate, 1) || gate != 'G') return 2;
    const char *error = NULL;
#ifdef FSEARCH_WORKER_ORACLE
    g_autoptr(FsearchHeadlessSnapshot) snapshot = argc==5?fsearch_headless_open_checkpoint(argv[1],argv[4],&error):fsearch_headless_open(argv[1], &error);
#else
    g_autoptr(FsearchHeadlessSnapshot) snapshot = argc==5?fsearch_headless_open_checkpoint(argv[1],argv[4],&error):fsearch_headless_open_catalog(argv[1], &error);
#endif
    if (!snapshot) {
        g_autofree char *body = g_strdup_printf("{\"status\":\"error\",\"error\":{\"code\":\"%s\"}}", error);
        send_frame(body, strlen(body)); return 1;
    }
    FsearchCatalogStatus ready_state={0};if(fsearch_headless_catalog(snapshot))fsearch_catalog_status(fsearch_headless_catalog(snapshot),&ready_state);
    g_autofree char *ready = argc==5?g_strdup_printf("{\"status\":\"ready\",\"snapshot_id\":\"%s\",\"checkpoint_sequence\":%llu}", fsearch_headless_identity(snapshot),(unsigned long long)ready_state.sequence)
        :g_strdup_printf("{\"status\":\"ready\",\"snapshot_id\":\"%s\"}", fsearch_headless_identity(snapshot));
    if (!send_frame(ready, strlen(ready))) return 1;
    CatalogWorker catalog={.snapshot=snapshot};
    for (;;) {
        uint32_t wire[7];
        if (!read_all(wire, sizeof(wire))) {catalog_cleanup(&catalog);return 0;}
        for (unsigned i = 0; i < 7; i++) wire[i] = ntohl(wire[i]);
        compact_poll(&catalog);checkpoint_poll(&catalog);
        if(wire[0]>=0x100){if(!catalog_command(&catalog,wire)){catalog_cleanup(&catalog);return 2;}continue;}
        if (wire[0] > 7 || wire[1] > 2 || wire[2] < 1 || wire[2] > 1000 || wire[3] < 1 || wire[3] > MAX_CANDIDATES
            || wire[4] < 512 || wire[4] > MAX_RESPONSE_BYTES || wire[5] > 4096 || wire[6] > 512) {catalog_cleanup(&catalog);return 2;}
        char query[4097] = {0}, extension[513] = {0};
        if (!read_all(query, wire[5]) || !read_all(extension, wire[6])) {catalog_cleanup(&catalog);return 2;}
        if (strlen(query) != wire[5] || strlen(extension) != wire[6] || !g_utf8_validate(query, -1, NULL)
            || !g_utf8_validate(extension, -1, NULL)) {catalog_cleanup(&catalog);return 2;}
        const char *kinds[] = {"all", "files", "folders"};
        Options options = {.query = query, .extension = (wire[0] & 4) ? extension : NULL, .kind = (char *)kinds[wire[1]],
            .path = wire[0] & 1, .match_case = wire[0] & 2, .limit = wire[2], .max_candidates = wire[3], .max_bytes = wire[4], .timeout_ms = 1000};
        g_autoptr(GString) response = fsearch_headless_search(&options, snapshot, &error);
        if (!response) response = g_string_new(NULL), g_string_printf(response,
            "{\"schema_version\":1,\"status\":\"error\",\"complete\":false,\"error\":{\"code\":\"%s\"},\"results\":[]}", error);
        if (!send_frame(response->str, response->len)) {catalog_cleanup(&catalog);return 1;}
    }
}
