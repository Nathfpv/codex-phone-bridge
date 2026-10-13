/* MIT License. Private Unix datagram PCM driver for Baresip 4.12. */
#include <re.h>
#include <rem.h>
#include <baresip.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <errno.h>
#include <string.h>
#include <stdio.h>
struct pcm { struct tmr timer; int fd; bool source; uint32_t rate, ptime; uint8_t ch; size_t count; int16_t samples[4096]; ausrc_read_h *readh; auplay_write_h *writeh; void *arg; struct sockaddr_un target; char path[104]; uint64_t ts, next; };
struct ausrc_st { struct pcm pcm; };
struct auplay_st { struct pcm pcm; };
static struct ausrc *source;
static struct auplay *player;
static void destroy(void *arg) { struct pcm *p=arg; tmr_cancel(&p->timer); if(p->fd>=0) close(p->fd); if(p->source && p->path[0]) unlink(p->path); }
static void tick(void *arg) {
 struct pcm *p=arg; struct auframe frame; memset(p->samples,0,p->count*2);
 if(p->source) { ssize_t n=recv(p->fd,p->samples,p->count*2,MSG_DONTWAIT); if(n<0) memset(p->samples,0,p->count*2); }
 auframe_init(&frame,AUFMT_S16LE,p->samples,p->count,p->rate,p->ch); frame.timestamp=p->ts; p->ts += (uint64_t)p->ptime*1000;
 if(p->source) p->readh(&frame,p->arg); else { p->writeh(&frame,p->arg); (void)sendto(p->fd,p->samples,p->count*2,MSG_DONTWAIT,(struct sockaddr *)&p->target,sizeof(p->target)); }
 p->next += p->ptime; uint64_t now=tmr_jiffies(); tmr_start(&p->timer,p->next>now?p->next-now:1,tick,p);
}
static int setup(struct pcm *p, const char *path, uint32_t rate,uint8_t ch,uint32_t ptime,int fmt) {
 if(!path || strlen(path)>=sizeof(p->path) || fmt!=AUFMT_S16LE || rate!=16000 || ch!=1 || ptime!=20) return EINVAL;
 p->rate=rate; p->ch=ch; p->ptime=ptime; p->count=rate*ch*ptime/1000; p->fd=socket(AF_UNIX,SOCK_DGRAM,0); if(p->fd<0) return errno;
 int buffer=262144; setsockopt(p->fd,SOL_SOCKET,SO_RCVBUF,&buffer,sizeof(buffer)); setsockopt(p->fd,SOL_SOCKET,SO_SNDBUF,&buffer,sizeof(buffer));
 fcntl(p->fd,F_SETFL,O_NONBLOCK); p->target.sun_family=AF_UNIX; str_ncpy(p->target.sun_path,path,sizeof(p->target.sun_path));
 if(p->source) { if(bind(p->fd,(struct sockaddr *)&p->target,sizeof(p->target))<0) return errno; str_ncpy(p->path,path,sizeof(p->path)); chmod(path,0600); }
 p->next=tmr_jiffies()+20;tmr_start(&p->timer,20,tick,p); return 0;
}
static int src_alloc(struct ausrc_st **out,const struct ausrc *as,struct ausrc_prm *prm,const char *dev,ausrc_read_h *rh,ausrc_error_h *eh,void *arg) {
 (void)as;(void)eh; struct ausrc_st *s=mem_zalloc(sizeof(*s),destroy); if(!s)return ENOMEM; s->pcm.fd=-1;s->pcm.source=true;s->pcm.readh=rh;s->pcm.arg=arg;
 int e=setup(&s->pcm,dev,prm->srate,prm->ch,prm->ptime,prm->fmt); if(e){mem_deref(s);return e;} *out=s;return 0;
}
static int play_alloc(struct auplay_st **out,const struct auplay *ap,struct auplay_prm *prm,const char *dev,auplay_write_h *wh,void *arg) {
 (void)ap;struct auplay_st *s=mem_zalloc(sizeof(*s),destroy);if(!s)return ENOMEM;s->pcm.fd=-1;s->pcm.writeh=wh;s->pcm.arg=arg;
 int e=setup(&s->pcm,dev,prm->srate,prm->ch,prm->ptime,prm->fmt);if(e){mem_deref(s);return e;}*out=s;return 0;
}
static int init(void) { int e=ausrc_register(&source,baresip_ausrcl(),"phoneaudio",src_alloc); if(e)return e;return auplay_register(&player,baresip_auplayl(),"phoneaudio",play_alloc); }
static int shutdown_module(void) { source=mem_deref(source);player=mem_deref(player);return 0; }
EXPORT_SYM const struct mod_export DECL_EXPORTS(phoneaudio)={"phoneaudio","audio",init,shutdown_module};
