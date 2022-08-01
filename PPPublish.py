#!/usr/bin/env python3
import os
from mutagen.mp3 import MP3
from datetime import datetime


tracks = []
Artist= "PATRISPREDICTUM"

Genre=""
feat=["PATRISPREDICTUM"]
Album=""



def getTracks():
	for i in os.listdir():
		if (i[-4:]==".mp3" or i[-4:]==".wav") and i!=Album+".mp3":
			if ". " in i:
				tracks.append(i[i.index('. '):-4].strip())
			else:
				try:
					int(i[0:2])
					i=i[2:]
				except:
					pass
				tracks.append(i[:-4])


	"""if "Prod." in i:
		start=i.index("Prod.")+6
		feat.append(i[start:i.index(")",start)])"""
def clearFolder(folder):
	try:
		os.mkdir(folder)
	except :
		for i in os.listdir(folder):
			#if i[i.index(". ")+2:-4] in tracks:
			if ". " in i:
				os.remove(folder+"/"+i)


def mp3():
	clearFolder(Album)
	i=0
	for file in os.listdir():
		if (file[-4:]==".mp3" or file[-4:]==".wav") and file!=Album	+".mp3":
			os.system("ffmpeg -i \"{}\" -i \"{}\" -map 0:0 -map 1:0 -b:a 320k -acodec libmp3lame -id3v2_version 3 -metadata title=\"{}\" -metadata track=\"{}\" -metadata album_artist=\"{}\" -metadata album=\"{}\" -metadata genre=\"{}\" -metadata artist=\"{}\" \"{}/{:02d}. {}.mp3\" -y".format(
				file,
				"cover.png"
				,tracks[i]
				,i+1
				,Artist
				,Album
				,Genre
				,", ".join(feat)
				,Album
				,i+1
				,tracks[i])
			)
			i+=1

def wav():
	clearFolder(Wavfolder)
	i=0
	for file in os.listdir():
		if (file[-4:]==".mp3" or file[-4:]==".wav") and file!=Album	+".mp3":
			os.system("ffmpeg -i \"{}\" -ar 44100 -ac 2 \"{}/{:02d}. {}.wav\" -y".format(
				file
				,Wavfolder
				,i+1
				,tracks[i])
			)
			i+=1

def Youtube():
	try:
		os.remove(Album+".mp4")
	except:
		pass
	audio = os.listdir(Wavfolder)
	vid = "-loop 1 -i Cover.png"
	if "vid.mp4" in os.listdir():
		vid = "-i vid.mp4"
	justaudio = "ffmpeg -i \"{}/{}\" {} -filter_complex \"[{}:0]concat=n={}:v=0:a=1[out]\" -map [out] -map {}:v -b:a 320k -acodec libmp3lame -c:v libx264 -tune stillimage -pix_fmt yuv420p -shortest \"{}.mp4\" -y".format(Wavfolder,"\" -i \"{}/".format(Wavfolder).join(audio), vid, ":0][".join([str(i) for i in range(len(audio))]), len(audio),len(audio), Album)
	os.system(justaudio)

def full():
	try:
		os.remove(Album +".mp3")
	except:
		pass
	audio = f"|{Album}/".join([i for i in os.listdir(Album) if i.endswith(".mp3")])
	justaudio = f"ffmpeg -i \"concat:{Album}/{audio}\" -c copy \"{Album}.mp3\" -y"
	print	(justaudio	)
	os.system(justaudio)

def description():
	try:
		os.remove("Description.txt")
	except:
		pass
	time = 0
	des = open("Description.txt", "w")
	des.write(Artist+"s new Release " + Album + " now on Youtube!\nEnjoy our latest Tunes UwU\n\nTimestamps:\n")	
	for i in os.listdir(Album):
		if i[-4:]==".mp3":
			audio = MP3(Album+"/"+i)
			date_time = datetime.fromtimestamp(time)
			des.write(date_time.strftime("%M:%S")+i[3:-4]+"\n")
			time+=audio.info.length

getTracks()

def all():
	mp3()
	wav()
	video()
	description()
	full()

def rename(name):
	global Album
	global Wavfolder
	Album=name
	Wavfolder = Album +" HQ"
	tracks.clear()
	getTracks()
	print("working on \"" + Album +"\"!")

cmd = "all()"

exits = ["q", "quit", "exit"]
tmp = os.getcwd().split("\\")[-1]
if ")" in tmp:
	tmp=" ".join(tmp.split(") ")[1:])
	
rename(tmp)
print("change name with name [Album name]")
while True:
	inp = input("PP/Publish~$ ")
	if inp in exits:
		break
	if inp.split(" ")[0]=="name":
		rename(" ".join(inp.split(" ")[1:]))
		continue
	if len(inp):
		cmd=inp+"()"
	eval(cmd)