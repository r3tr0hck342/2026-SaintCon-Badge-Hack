// SC_<A>_<B> dict x dict brute for the REABadge UNLOCK hash. usage: dd words.txt [prefix]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <ctype.h>
#include "consts.h"  // python3 -I scripts/consts.py scripts/badge.py fw_dump/flash.bin > consts.h
static uint64_t T[64]; static int nt;
static inline uint64_t H(const uint8_t *d, int n){
  uint64_t h=seed^X; int i=0;
  for(;i+8<=n;i+=8){uint64_t w; memcpy(&w,d+i,8); h=((h^w)*K1)+C1;}
  if(i<n){uint64_t w=0; memcpy(&w,d+i,n-i); h^=w;}
  h=h*K1+C1; h^=n; h=h*K2+C2; h^=h>>33; h=h*K1+C1; h^=h>>29; h=h*K2+C2; h^=h>>32; return h;
}
int main(int c,char**v){
  FILE*f=fopen("consts.h","r"); char ln[256];
  while(fgets(ln,256,f)) if(!strncmp(ln,"// bit",6)){unsigned long long x; int k; sscanf(ln,"// bit %d 0x%llx",&k,&x); T[nt++]=x;}
  fclose(f);
  const char*pre=c>2?v[2]:"SC_";
  char**W=malloc(sizeof(char*)*500000); int*L=malloc(sizeof(int)*500000); int n=0;
  f=fopen(v[1],"r");
  while(fgets(ln,256,f)){int l=0,ok=1; for(;ln[l]&&ln[l]!='\n'&&ln[l]!='\r';l++){if(!isalpha((unsigned char)ln[l]))ok=0; ln[l]=toupper(ln[l]);} ln[l]=0;
    if(ok&&l>=2&&l<=16){W[n]=strdup(ln);L[n]=l;n++;}}
  fprintf(stderr,"%d words, %.3g pairs\n",n,(double)n*n);
  int pl=strlen(pre);
  #pragma omp parallel for schedule(dynamic,64)
  for(int a=0;a<n;a++){ uint8_t buf[64]; memcpy(buf,pre,pl); memcpy(buf+pl,W[a],L[a]); int p=pl+L[a]; buf[p++]='_';
    for(int b=0;b<n;b++){ memcpy(buf+p,W[b],L[b]); uint64_t h=H(buf,p+L[b]);
      for(int t=0;t<nt;t++) if(h==T[t]){
        #pragma omp critical
        {printf("HIT %.*s\n",p+L[b],buf); fflush(stdout);}
      }}}
  return 0;
}
