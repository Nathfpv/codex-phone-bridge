/* MIT License. Owner-only Unix stream control for Baresip 4.12.
 * JSON netstrings, bounded buffers, restricted commands. No TCP listener.
 */
#include <re.h>
#include <baresip.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#define LIMIT 65536
static int listener=-1, client=-1;
static struct tmr timer;
static char socket_path[104];
static unsigned char incoming[LIMIT], outgoing[LIMIT];
static size_t used, queued;
static int append_text(const char *text,size_t length,void *arg) { return mbuf_write_mem(arg,(const uint8_t *)text,length); }
static void disconnect(void) { if(client>=0)close(client);client=-1;used=queued=0; }
static void transmit(struct odict *dict) {
 if(client<0)return;
 struct mbuf *buf=mbuf_alloc(1024);if(!buf)return;
 struct re_printf printer={append_text,buf};
 if(!json_encode_odict(&printer,dict)) {
  char prefix[32];int n=snprintf(prefix,sizeof(prefix),"%zu:",buf->end);
  if(n>0 && queued+(size_t)n+buf->end+1<LIMIT) {
   memcpy(outgoing+queued,prefix,(size_t)n);queued+=(size_t)n;
   memcpy(outgoing+queued,buf->buf,buf->end);queued+=buf->end;outgoing[queued++]=',';
  } else disconnect();
 }
 mem_deref(buf);
}
static bool permitted(const char *name) { return !str_cmp(name,"dial") || !str_cmp(name,"hangup") || !str_cmp(name,"accept") || !str_cmp(name,"reginfo"); }
static void execute(const unsigned char *body,size_t length) {
 struct odict *input=NULL,*output=NULL;struct mbuf *text=NULL;char *data=NULL;
 if(json_decode_odict(&input,16,(const char *)body,length,8)) {disconnect();return;}
 const char *name=odict_string(input,"command"),*params=odict_string(input,"params"),*token=odict_string(input,"token");
 int err=EINVAL;char command[4096];
 text=mbuf_alloc(2048);
 if(text && name && permitted(name) && (!params || strlen(params)<3000) && !strchr(name,'\n') && (!params || (!strchr(params,'\n') && !strchr(params,'\r')))) {
  int n=snprintf(command,sizeof(command),"%s%s%s",name,params?" ":"",params?params:"");
  struct re_printf printer={append_text,text};err=cmd_process_long(baresip_commands(),command,(size_t)n,&printer,NULL);
 }
 if(text){text->pos=0;(void)mbuf_strdup(text,&data,text->end);}
 if(!odict_alloc(&output,8)) {
  (void)odict_entry_add(output,"response",ODICT_BOOL,true);
  (void)odict_entry_add(output,"ok",ODICT_BOOL,!err);
  (void)odict_entry_add(output,"data",ODICT_STRING,data?data:"");
  if(token)(void)odict_entry_add(output,"token",ODICT_STRING,token);
  transmit(output);
 }
 mem_deref(data);mem_deref(text);mem_deref(output);mem_deref(input);
}
static void events(enum bevent_ev ev,struct bevent *event,void *arg) {
 (void)ev;(void)arg;struct odict *dict=NULL;
 if(client<0 || odict_alloc(&dict,16))return;
 if(!odict_entry_add(dict,"event",ODICT_BOOL,true) && !bevent_odict_encode(dict,event))transmit(dict);
 mem_deref(dict);
}
static void poll_control(void *arg) {
 (void)arg;
 if(client<0) {client=accept(listener,NULL,NULL);if(client>=0){fcntl(client,F_SETFL,O_NONBLOCK);int enabled=1;setsockopt(client,SOL_SOCKET,SO_NOSIGPIPE,&enabled,sizeof(enabled));used=queued=0;}}
 if(client>=0) {
  ssize_t count=recv(client,incoming+used,LIMIT-used,MSG_DONTWAIT);
  if(count==0 || (count<0 && errno!=EAGAIN && errno!=EWOULDBLOCK))disconnect();
  else if(count>0) {
   used+=(size_t)count;
   while(client>=0 && used) {
    size_t colon=0,length=0;
    while(colon<used && incoming[colon]>='0' && incoming[colon]<='9') {
     length=length*10+incoming[colon]-'0';++colon;if(colon>6 || length>LIMIT-16){disconnect();break;}
    }
    if(client<0)break;
    if(colon==used)break;
    if(!colon || incoming[colon]!=':'){disconnect();break;}
    size_t total=colon+1+length+1;if(used<total)break;
    if(incoming[total-1]!=','){disconnect();break;}
    execute(incoming+colon+1,length);if(client<0)break;
    memmove(incoming,incoming+total,used-total);used-=total;
   }
   if(used==LIMIT)disconnect();
  }
 }
 if(client>=0 && queued) {
  ssize_t n=send(client,outgoing,queued,MSG_DONTWAIT);
  if(n>0){memmove(outgoing,outgoing+n,queued-(size_t)n);queued-=(size_t)n;}
  else if(n<0 && errno!=EAGAIN && errno!=EWOULDBLOCK)disconnect();
 }
 tmr_start(&timer,10,poll_control,NULL);
}
static int init(void) {
 if(conf_get_str(conf_cur(),"phonecontrol_socket",socket_path,sizeof(socket_path)))return EINVAL;
 struct sockaddr_un addr;memset(&addr,0,sizeof(addr));addr.sun_family=AF_UNIX;
 if(strlen(socket_path)>=sizeof(addr.sun_path))return EINVAL;
 str_ncpy(addr.sun_path,socket_path,sizeof(addr.sun_path));
 listener=socket(AF_UNIX,SOCK_STREAM,0);if(listener<0)return errno;
 fcntl(listener,F_SETFL,O_NONBLOCK);
 if(bind(listener,(struct sockaddr *)&addr,sizeof(addr))<0 || listen(listener,1)<0){int err=errno;close(listener);listener=-1;return err;}
 chmod(socket_path,0600);int err=bevent_register(events,NULL);if(err)return err;
 tmr_start(&timer,10,poll_control,NULL);return 0;
}
static int close_module(void) {tmr_cancel(&timer);bevent_unregister(events);disconnect();if(listener>=0)close(listener);listener=-1;unlink(socket_path);return 0;}
EXPORT_SYM const struct mod_export DECL_EXPORTS(phonecontrol)={"phonecontrol","application",init,close_module};
