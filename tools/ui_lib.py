# SPDX-License-Identifier: GPL-3.0-or-later
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import statistics,os
SS=4
REG="/usr/share/fonts/noto/NotoSans-Regular.ttf"; LIGHT="/usr/share/fonts/noto/NotoSans-Light.ttf"
def render(txt,size,color,track=0.0,path=REG,stroke=0,shadow=True,sh_off=(1,1),sh_blur=1.0,sh_alpha=190):
    """RGBA image of the text (supersampled), with drop shadow; returns (img, (ox,oy)) where img includes padding for shadow"""
    f=ImageFont.truetype(path,size*SS)
    w=int(sum(f.getlength(c)+track*SS for c in txt))+8*SS; h=int(size*SS*2)
    m=Image.new('L',(w,h),0); d=ImageDraw.Draw(m); x=4*SS
    for c in txt:
        d.text((x,h//4),c,font=f,fill=255,stroke_width=stroke,stroke_fill=255); x+=f.getlength(c)+track*SS
    bb=m.getbbox(); m=m.crop(bb)
    W,H=max(1,m.size[0]//SS),max(1,m.size[1]//SS)
    m=m.resize((m.size[0]//SS*SS or SS,m.size[1]//SS*SS or SS)).resize((W,H),Image.LANCZOS)
    pad=4; out=Image.new('RGBA',(W+2*pad,H+2*pad),(0,0,0,0))
    if shadow:
        sm=Image.new('L',out.size,0); sm.paste(m,(pad+sh_off[0],pad+sh_off[1])); sm=sm.filter(ImageFilter.GaussianBlur(sh_blur))
        sm=sm.point(lambda v:int(v*sh_alpha/255)); sh=Image.new('RGBA',out.size,(0,0,0,255)); sh.putalpha(sm); out.alpha_composite(sh)
    col=Image.new('RGBA',m.size,tuple(color)+(255,)); layer=Image.new('RGBA',out.size,(0,0,0,0)); layer.paste(col,(pad,pad),m); out.alpha_composite(layer)
    return out
def put(im,txt,x,cy,size,color,align='left',**kw):
    t=render(txt,size,color,**kw); w,h=t.size
    if align=='center': x0=int(x-w/2)
    elif align=='right': x0=int(x-w)
    else: x0=int(x)-4
    im.alpha_composite(t,(x0,int(cy-h/2)))
def bright_bbox(im,box,athr=40,sthr=330):
    px=im.load(); x0,y0,x1,y1=box; xs=[];ys=[]
    for y in range(y0,y1):
        for x in range(x0,x1):
            r,g,b,a=px[x,y]
            if a>=athr and (r+g+b)>=sthr: xs.append(x);ys.append(y)
    return (min(xs),min(ys),max(xs),max(ys)) if xs else None
def clear(im,box):
    x0,y0,x1,y1=box; px=im.load()
    for y in range(max(0,y0),min(im.size[1],y1+1)):
        for x in range(max(0,x0),min(im.size[0],x1+1)): px[x,y]=(0,0,0,0)
def save_bmp(im,path): im.convert('RGBA').save(path,format='BMP')
