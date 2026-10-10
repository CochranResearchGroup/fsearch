/* Owned-test-only gate: hold the first checkpoint write while wire queries run. */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <dlfcn.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
ssize_t pwrite(int fd,const void *buffer,size_t size,off_t offset) {
    static ssize_t (*real_pwrite)(int,const void*,size_t,off_t);
    if(!real_pwrite)real_pwrite=dlsym(RTLD_NEXT,"pwrite64");
    const char *gate=getenv("FSEARCH_CHECKPOINT_TEST_GATE");
    if(gate&&offset==0&&size>=8&&!memcmp(buffer,"FSCG0001",8)) {
        struct timespec pause={0,10000000};unsigned tries=0;
        while(access(gate,F_OK)==0){if(++tries>500){errno=ETIMEDOUT;return -1;}nanosleep(&pause,NULL);}
    }
    return real_pwrite(fd,buffer,size,offset);
}
