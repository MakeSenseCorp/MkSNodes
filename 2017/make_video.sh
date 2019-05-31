#!/bin/bash

cd /home/ykiveish/mks/mksnodes/2017/video_fs/images/$1
ffmpeg -r 1/1 -i %d.jpg -c:v libx264 -vf fps=1 -pix_fmt yuv420p out.mp4
rm *.jpg
cd -
mv /home/ykiveish/mks/mksnodes/2017/video_fs/images/$1/out.mp4 /home/ykiveish/mks/mksnodes/2017/video_fs/videos/out_$(date -d "today" +"%Y%m%d%H%M")
