#!/bin/bash

cd /tmp/video_fs/images/$1
#ffmpeg -r 1/1 -i %d.jpg -c:v libx264 -vf fps=1 -pix_fmt yuv420p out.mp4
ffmpeg -r 1 -i %d.jpg -vcodec mpeg4 -y out.mp4
#rm *.jpg
cd -
mv /tmp/video_fs/images/$1/out.mp4 /tmp/video_fs/videos/out_$(date -d "today" +"%Y%m%d%H%M")
