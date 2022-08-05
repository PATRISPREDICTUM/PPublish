#!/usr/bin/env python3
import os
import subprocess
import time
import copy
from datetime import datetime
import hashlib
import pickle
import re
import audioread

current_states = {}
new_state = {}
save = {}


def getFirst_Letter(string):
	match = re.search('[a-zA-Z0-9][^)]+', string)
	if match==None:
		return None
	return match.start()

class File:
	def __init__(self, path):
		self.path=path
		self.valid=os.path.isfile(path)
		if self.valid:
			self.md5=self.hash()

	def hash(self):
		with open(self.path, "rb") as f:
			file_hash = hashlib.md5()
			while chunk := f.read(8192):
				file_hash.update(chunk)

			return file_hash.hexdigest()

	def __eq__(self, Other):
		if type(Other)==type(self):
			return self.md5==Other.md5
		return False


class Track(File):
	def __init__(self, file, index):
		super().__init__(file)
		self.index=index
		self.load()

	def load(self):
		if self.valid:
			self.length = self.getlength()
		self.name=self.load_name()

	def move(self, path):
		self.path=path
		self.load()

	def load_name(self):
		file = self.path.split("/")[-1]
		# get Name begining
		start=getFirst_Letter(file)
		if start==None:
			return "Unknown"

		# get name end
		end=file.rfind(".")
		return file[start:end]

	def getlength(self):
		return audioread.audio_open(self.path).duration
	def __eq__(self, Other):
		if type(Other)==type(self):
			return self.md5==Other.md5
		return False
#updates
class RenameTrack:
	def __init__(self, md5, new_path):
		self.md5=md5
		self.new_path = new_path

	def apply(self, state):
		track = getTrackByMD5(state["Tracks"], self.md5)
		if track == None:
			print("[ERROR] Could not find Track in state hash: "+self.md5)
			return True
		track.move(self.new_path)
		return False

class RenameAlbum:
	def __init__(self, new_name):
		self.new_name=new_name
	def apply(self, state):
		state["Album"]=self.new_name
		return False

class ChangePath:
	def __init__(self, module, path):
		self.module=module
		self.path=path
	def apply(self, state):
		state[self.module+"_path"]=self.path
		return False

class UpdateTrack:
	def __init__(self, Track):
		self.track = Track
	def apply(self, state):
		return False

class NewTrack:
	def __init__(self, Track):
		self.track = Track
	def apply(self, state):
		state["Tracks"].append(copy.deepcopy(self.track))
		return False

class DeleteTrack:
	def __init__(self, Track):
		self.track = Track
	def apply(self, state):
		state["Tracks"].remove(self.track)
		return False
#
#class UpateCover:
#	def __init__(self, path):
#		self.path=path

class UpdateVideo:
	def __init__(self, path):
		self.path=path
	def apply(self, state):
		state["Video"]=self.path
		return False

class Updatemp3tags:
	def __init__(self, tags):
		self.tags = tags
	def apply(self, state):
		state["tags"]=copy.copy(self.tags)
		return False

class Reorder:
	def __init__(self, md5, index):
		self.md5=md5
		self.index = index
	def apply(self, state):
		track = getTrackByMD5(state["Tracks"], self.md5)
		if track == None:
			print("[ERROR] Could not find Track in state hash: "+self.md5)
			return True
		track.index = self.index
		return False

class Initilize:
	def __init__(self, path, module):
		self.path=path
		self.module=module
	def apply(self, state):
		state[self.module+"_path"]=self.path
		return False

class Start:
	def __init__(self):
		pass

class End:
	def __init__(self):
		pass

class Clear:
	def __init__(self):
		pass
	def apply(self, state):
		pass



def getTrackByMD5(Tracks, md5):
	same = [t for t in Tracks if t.md5==md5]
	if len(same)==0:
		return None
	if len(same)>1:
		print("[WARNING] Duplicate Tracks found!")
		print(same)
	return same[0]

def getTrackByName(Tracks, name):
	same = [t for t in Tracks if t.name==name]
	if len(same)==0:
		return None
	if len(same)>1:
		print("[WARNING] Duplicate Tracks found!")
		print(same)
	return same[0]

def track_add(Tracks, path):
	track = Track(path, len(Tracks)+1)
	if not track.valid:
		print("File does not exist")
		return
	dup = getTrackByMD5(Tracks, track.md5)
	twin = getTrackByName(Tracks, track.name)
	if dup:
		if dup.path!=track.path:
			print("sub" + dup.path + " ->" + track.path)
			dup.move(path)
	elif twin:
		print("sub " + twin.path + " hash!")
		twin.md5=track.md5
	else:
		print("Loading Track "+track.path)
		Tracks.append(track)

def track_rm(Tracks, track):
	index= track.index
	print("Removed "+track.name)
	Tracks.remove(track)
	for track in Tracks:
		if track.index>index:
			track.index-=1

def track_rmn(Tracks, name):
	track = getTrackByName(Tracks, name)
	if track == None:
		print("[ERROR] Could not find Track \""+name+"\"")
		return
	track_rm(Tracks, track)

def track_rmi(Tracks, index):
	num = int(index)
	tracks = [i for i in Tracks if i.index==num]
	for track in tracks:
		track_rm(Tracks, track)

def Tracks_sort(Tracks):
	Tracks.sort(key=lambda x: x.index)


audio_fmt = ["mp3", "wav"]

def dir_prep(directory):
	directory=directory.strip()
	if len(directory)==0:
		directory="."

	directory.replace("\\","/")
	if directory[-1]!="/":
		directory+="/"
	return directory

def dir_add(state, directory, save=True):

	directory = dir_prep(directory)
	if not directory in state["dirs"] and save:
		state["dirs"].append(directory)

	# Get all songs in directory
	for f in os.listdir(directory):
		if os.path.isfile(directory+f) and f.split(".")[-1] in audio_fmt:
			track_add(state["Tracks"], directory+f)

def dir_rm(state, directory):

	directory = dir_prep(directory)
	if directory in state["dirs"]:
		state["dirs"].remove(directory)

	# Get all songs in directory
	for track in reversed(state["Tracks"]):
		if track.path.startswith(directory):
			track_rm(state["Tracks"], track)

def getName():
	folder = os.getcwd().replace("\\","/").split("/")[-1]
	start = getFirst_Letter(folder)
	return folder[start:]

image_fmt = ["png", "bmp", "jpg", "tiff"]
video_fmt = ["avi", "mp4", "flv", "mkv"]
def getCover():
	tmp = [f for f in os.listdir() if len(f.split("."))==2]
	for file in tmp:
		l = file.lower().split(".")
		if l[0]=="cover" and l[1] in image_fmt:
			return File(file)
	return None

def getVideo():
	tmp = [f for f in os.listdir() if len(f.split("."))==2]
	for file in tmp:
		l = file.lower().split(".")
		if l[0].startswith("vid") and l[1] in video_fmt:
			return File(file)
	return getCover()

def setName(conf, name):
	conf["Album"] = name
	conf["mp3_path"] = name
	conf["wav_path"] = name + " HQ"
	conf["video_path"] = name + ".mp4"

def conf_detect(conf):
	dir_add(conf, "./", False)
	#album name
	setName(conf, getName())
	conf["tags"]["Cover"]  = getCover()
	conf["Video"] = getVideo()

def Rename(old_name, new_name):
	changed=False
	while not changed:
		try:
			os.rename(old_name, new_name)
			changed=True
		except PermissionError:
			print(old_name+" in use please resolve")
			time.Sleep(1)
			continue
		except Exception as e:
			print("Could not rename : "+str(e))
			return True
	return False

def Delete(file):
	changed=False
	while not changed:
		try:
			os.remove(file)
			changed=True
		except PermissionError:
			print(old_name+" in use please resolve")
			time.Sleep(1)
			continue
		except FileNotFoundError:
			break
		except Exception as e:
			print("Could not remove : "+str(e))
			return True
	return False

def dir_Delete(file):
	changed=False
	while not changed:
		try:
			os.rmdir(file)
			changed=True
		except PermissionError:
			print(old_name+" in use please resolve")
			time.Sleep(1)
			continue
		except FileNotFoundError:
			break
		except Exception as e:
			print("Could not remove : "+str(e))
			return True
	return False

def Reset(module):
	global current_states
	module.clear()
	#current_states[module.name]=conf_default()
	#module.state_set(current_states[module.name])


class module:
	def __init__(self):
		self.name = type(self).__name__

	def state_set(self, state):
		self.state = state
		self.load()

	def load(self):
		self.Tracks = self.state["Tracks"]
		self.Album = self.state["Album"]
	def start(self):
		pass
	def end(self):
		pass
	def verify(self, new_state):
		pass


class mp3(module):
	def __init__(self):
		super().__init__()

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Cover = self.state["tags"]["Cover"]
		self.tags = self.state["tags"]

	def retag_track(self, track):
		if not track in self.retag and not track in self.rerender:
			self.retag.append(track)

	def rerender_track(self, track):
		if track in self.retag:
			self.retag.remove(track)
		if not track in self.rerender:
			self.rerender.append(track)

	def start(self):
		self.retag = []
		self.rerender = []

	def end(self):
		for track in self.rerender:
			self.Render(track)

		for track in self.retag:
			self.ReTag(track)

	def verify(self, new_state):
		if not os.path.exists(self.path):
			Reset(self)
		else:
			for track in reversed(self.Tracks):
				if not self.getName(track.index, track.name) in os.listdir(self.path):
					self.Tracks.remove(track)

	def handle(self, update):
		self.load()
		task = type(update).__name__
		if task == "RenameTrack":
			track = getTrackByMD5(self.Tracks, update.md5)
			if track == None:
				print("[ERROR] Could not find Track in state hash: "+update.md5)
				return True

			old_name = self.getName(track.index,track.name)
			if not old_name in os.listdir(self.path):
				print("[ERROR] Could not find Track in folder \""+track.path+"\"")
				return True

			new_name = self.getName(track.index, update.new_name)
			Rename(os.path.join(self.path,old_name), os.path.join(self.path, new_name))
			self.retag_track(track)

		elif task == "ChangePath":
			if update.module==self.name:
				return Rename(self.path, update.path)

		elif task == "NewTrack":
			self.rerender_track(update.track)

		elif task == "UpdateTrack":
			track = getTrackByName(self.Tracks, update.track.name)
			if track == None:
				print("[ERROR] Could not find Track \""+update.track.name+"\"")
				return True
			self.rerender_track(track)
			track.md5=update.track.md5

		elif task == "DeleteTrack":
			self.delete(update.track)

		elif task == "Updatemp3tags":
			for track in self.Tracks:
				self.retag_track(track)

		elif task == "Reorder":
			track = getTrackByMD5(self.Tracks, update.md5)
			if track == None:
				print("[ERROR] Could not find track! hash: "+update.md5)
				return True

			old_name = self.getName(track.index,track.name)
			if not old_name in os.listdir(self.path):
				print("[ERROR] Could not find Track in folder \""+old_name+"\"")
				return True

			new_name = self.getName(update.index,track.name)
			Rename(os.path.join(self.path,old_name), os.path.join(self.path, new_name))

			self.retag_track(track)

		elif task == "Initilize":
			try:
				os.mkdir(update.path)
			except:
				pass

		elif task == "Clear":
			clear()



		return False

	def getName(self, index, name):
		return str(index)+". "+name+".mp3"

	def ReTag(self, track):
		name=self.getName(track.index,track.name)
		if not name in os.listdir(self.path):
			print("[ERROR] could not find Track \""+track.name+"\"")
			return True
		if Rename(os.path.join(self.path, name), os.path.join(self.path, "tmp_"+name)):
			return True

		os.system("ffmpeg -i \"{}\" -i \"{}\" -map 0:0 -map 1:0 -c:a copy -id3v2_version 3 -metadata title=\"{}\" -metadata track=\"{}\" -metadata album_artist=\"{}\" -metadata album=\"{}\" -metadata genre=\"{}\" -metadata artist=\"{}\" \"{}\" -y".format(
				os.path.join(self.path,"tmp_"+name),
				self.Cover.path,
				track.name,
				track.index,
				self.tags["Artist"],
				self.Album,
				self.tags["Genre"],
				", ".join(self.tags["feat"]),
				os.path.join(self.path,
				self.getName(track.index, track.name)))
			)
		Delete(os.path.join(self.path, "tmp_"+name))

	def Render(self, track):
		os.system("ffmpeg -i \"{}\" -i \"{}\" -map 0:0 -map 1:0 -b:a 320k -acodec libmp3lame -id3v2_version 3 -metadata title=\"{}\" -metadata track=\"{}\" -metadata album_artist=\"{}\" -metadata album=\"{}\" -metadata genre=\"{}\" -metadata artist=\"{}\" \"{}\" -y".format(
				track.path,
				self.Cover.path,
				track.name,
				track.index,
				self.tags["Artist"],
				self.Album,
				self.tags["Genre"],
				", ".join(self.tags["feat"]),
				os.path.join(self.path,
				self.getName(track.index, track.name)))
			)

	def delete(self, Track):
		Delete(os.path.join(self.path,self.getName(Track.index,Track.name)))

	def clear(self):
		for track in self.Tracks:
			self.delete(track)
		self.Tracks.clear()
		dir_Delete(self.path)


class wav(module):
	def __init__(self):
		super().__init__()

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Cover = self.state["tags"]["Cover"]
		self.tags = self.state["tags"]

	def verify(self, new_state):
		if not os.path.exists(self.path):
			Reset(self)
		else:
			for track in reversed(self.Tracks):
				if not self.getName(track.index, track.name) in os.listdir(self.path):
					self.Tracks.remove(track)


	def handle(self, update):
		self.load()
		task = type(update).__name__
		if task == "RenameTrack":
			track = getTrackByMD5(self.Tracks, update.md5)
			if track == None:
				print("[ERROR] Could not find Track in state hash: "+update.md5)
				return True

			old_name = self.getName(track.index,track.name)
			if not old_name in os.listdir(self.path):
				print("[ERROR] Could not find Track in folder \""+old_name+"\"")
				return True

			new_name = self.getName(track.index, update.new_name)
			Rename(os.path.join(self.path,old_name), os.path.join(self.path, new_name))
			track.name=update.new_name

		elif task == "ChangePath":
			if update.module==self.name:
				return Rename(self.path, update.path)

		elif task == "NewTrack":
			self.Render(update.track)

		elif task == "UpdateTrack":
			track = getTrackByName(self.Tracks, update.track.name)
			if track == None:
				print("[ERROR] Could not find Track \""+update.track.name+"\"")
				return True
			self.Render(track)
			track.md5=update.track.md5

		elif task == "DeleteTrack":
			self.delete(update.track)

		elif task == "Reorder":
			track = getTrackByMD5(self.Tracks, update.md5)
			if track == None:
				print("[ERROR] Could not find track! hash: "+update.md5)
				return True

			old_name = self.getName(track.index,track.name)
			if not old_name in os.listdir(self.path):
				print("[ERROR] Could not find Track in folder \""+old_name+"\"")
				return True

			track.index=update.index
			new_name = self.getName(track.index,track.name)
			Rename(os.path.join(self.path,old_name), os.path.join(self.path, new_name))

		elif task == "Initilize":
			try:
				os.mkdir(update.path)
			except:
				pass

		elif task == "Clear":
			clear()


		return False

	def getName(self, index, name):
		return str(index)+". "+name+".wav"

	def Render(self, track):
		os.system("ffmpeg -i \"{}\" -ar 44100 -ac 2 \"{}\" -y".format(
				track.path,
				os.path.join(self.path,
				self.getName(track.index, track.name)))
			)

	def delete(self, Track):
		Delete(os.path.join(self.path,self.getName(Track.index,Track.name)))

	def clear(self):
		for track in self.Tracks:
			self.delete(track)
		self.Tracks.clear()
		dir_Delete(self.path)

class video(module):
	def __init__(self):
		super().__init__()
		self.jobs = [self.Render_video, self.Render_audio, self.Render]

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Video = self.state["Video"]


	def start(self):
		self.job = 0

	def end(self):
		if self.job:
			res = self.jobs[self.job-1]()
			self.state["output"]=File(self.path)
			print("New Hash: " + self.state["output"].md5)
			return res
		return False

	def search_sub(self, new_state):
		check = self.state["output"]
		found = False
		for file in os.listdir():
			if not os.path.isfile(file):
				continue
			print("candidate " + file)
			file=File(file)
			if file==check:
				print("New path " + file.path)
				self.state[module.name+"_path"]=file.path
				found=True
				break
		if not found:
			print("Noghing Found")
			Reset(self)

	def verify(self, new_state):
		if not "output" in self.state:
			return
		check = self.state["output"]
		if not check.valid:
			print("Wasnt Valid")
			Reset(self)
			return
		print("hash: " + check.md5)
		current = File(self.path)
		if not current.valid:
			print("file moved")
			self.search_sub(new_state)
		elif current!=check:
			print("hash: " + current.md5)
			print("file edit")
			self.search_sub(new_state)
		return

	def handle(self, update):
		self.load()
		task = type(update).__name__

		if task == "ChangePath":
			if update.module==self.name:
				Rename(self.path, update.path)

		elif task == "NewTrack":
			self.job=3

		elif task == "UpdateTrack":
			self.job=3

		elif task == "DeleteTrack" or task == "Reorder":
			if self.job==0 or self.job==2:
				self.job=2
			else:
				self.job=3

		elif task == "UpdateVideo":
			if self.job==0 or self.job==1:
				self.job=1
			else:
				self.job=3

		elif task == "Clear":
			clear()

		return False

	def Render(self):
		if not len(self.Tracks):
			return
		self.Tracks.sort(key=lambda x: x.index)
		audio = [ i.path for i in self.Tracks]
		vid_fmt = self.Video.path.split(".")[-1]
		render = "-stream_loop -1"
		if vid_fmt in image_fmt:
			render = "-loop 1"

		video_render = "{} -i {} -map {}:v".format(render, self.Video.path, len(audio))

		os.system("ffmpeg -i \"{}\" {} -filter_complex \"[{}:0]concat=n={}:v=0:a=1[out]\" -map [out] -b:a 320k -tune stillimage -acodec libmp3lame -c:v libx264 -pix_fmt yuv420p -shortest \"{}\" -y".format( "\" -i \"".join(audio), video_render, ":0][".join([str(i) for i in range(len(audio))]), len(audio), self.path)
			)
	def Render_audio(self):
		if not len(self.Tracks):
			return
		Tracks_sort(self.Tracks)
		audio = [ i.path for i in self.Tracks]
		if Rename(self.path, "tmp_"+self.path):
			return True
		os.system("ffmpeg -i \"{}\" -i \"{}\" -filter_complex \"[{}:0]concat=n={}:v=0:a=1[out]\" -map [out] -map {}:v -c:v copy -b:a 320k -acodec libmp3lame -pix_fmt yuv420p -shortest \"{}\" -y".format(
			"\" -i \"".join(audio), "tmp_"+self.path, ":0][".join([str(i) for i in range(len(audio))]), len(audio),len(audio), self.path)
			)
		Delete("tmp_"+self.path)

	def Render_video(self):
		if not len(self.Tracks):
			return
		vid_fmt = self.Video.path.split(".")[-1]
		render = "-stream_loop -1"
		if vid_fmt in image_fmt:
			render = "-loop 1"

		video_render = "{} -i {}".format(render, self.Video.path, len(audio))

		if Rename(self.path, "tmp_"+self.path):
			return True
		os.system("ffmpeg -i \"{}\" {} -map 0:a -map 1:v -b:a 320k -c:a copy -pix_fmt yuv420p -shortest \"{}\" -y".format(
			"tmp_"+self.path, video_render, self.path)
			)
		Delete("tmp_"+self.path)

	def clear(self):
		self.Tracks.clear()
		Delete(self.path)
		Delete("tmp_"+self.path)


modules = [ mp3(), wav(), video() ]

def conf_default():
	conf = {}

	conf["Tracks"] = []
	conf["Album"] = ""
	conf["dirs"] = []

	#mp3 tags
	conf["tags"]={}
	conf["tags"]["Artist"] = "PATRIS PREDICTUM"
	conf["tags"]["Genre"]  = "dominationdead"
	conf["tags"]["feat"]   = []
	conf["tags"]["Cover"]  = None
	conf["Video"] = None

	# module conf
	conf["description_path"] = "Description.txt"
	for module in modules:
		conf[module.name+"_path"] = ""

	return conf

def getDiff(old_state, new_state):
	diff = []
	if old_state["tags"]!=new_state["tags"]:
		diff.append(Updatemp3tags(new_state["tags"]))

	if old_state["Album"]!=new_state["Album"]:
		diff.append(RenameAlbum(new_state["Album"]))
		diff.append(Updatemp3tags(new_state["tags"]))

	for module in modules:
		if module.name+"_path" in old_state:
			if new_state[module.name+"_path"]!=old_state[module.name+"_path"]:
				diff.append(ChangePath(module.name, new_state[module.name+"_path"]))

	if old_state["Video"]!=new_state["Video"]:
		diff.append(UpdateVideo(new_state["Video"]))

	for track in old_state["Tracks"]:
		if track not in new_state["Tracks"]:
			Found=False
			for new_track in new_state["Tracks"]:
				if track.name==new_track.name:
					Found=True
					break
			if not Found:
				diff.append(DeleteTrack(track))
		else:
			for new_track in new_state["Tracks"]:
				if (track == new_state or track.name==new_track.name) and track.index!=new_track.index:
					diff.append(Reorder(track.md5, new_track.index))
				if track==new_track and track.name!=new_track.name:
					diff.append(RenameTrack(track.md5, new_track.name))


	for track in new_state["Tracks"]:
		if not track in old_state["Tracks"]:
			Found=False
			for old_track in old_state["Tracks"]:
				if track.name==old_track.name:
					diff.append(UpdateTrack(old_track))
					Found=True
					break
			if not Found:
				diff.append(NewTrack(track))
	return diff

def module_run(current_state, new_state, module):
	module.verify(new_state) # veriy Environment befor execution
	# if no path set initilize
	if not len(module.path):
		init = Initilize(new_state[module.name+"_path"], module.name)
		module.handle(init)
		init.apply(current_state)
	module.start() # signal start of transactions
	diffs = getDiff(current_state, new_state)
	# pass each change to module handler
	for diff in diffs:
		print("Handeling "+ type(diff).__name__ + " by " + module.name)
		if module.handle(diff):
			break
		diff.apply(current_state) # apply difference
	module.end()


savefile = ".ppub"
def pub_save():
	save["current_states"]=current_states
	save["new_state"]=new_state
	pickle.dump(save, open(savefile, "wb"))

if savefile in os.listdir():
	save = pickle.load(open(savefile, "rb"))

	current_states = save["current_states"]
	new_state = save["new_state"]


	for module in modules:
		if not module.name in current_states:
			current_states[module.name] = conf_default()
			new_state[module.name+"_path"]=""
		module.state_set(current_states[module.name])

	for directory in new_state["dirs"]:
		dir_add(new_state, directory)
else:
	print("---Analyzing Environment---")
	new_state = conf_default()

	conf_detect(new_state)
	for module in modules:
		current_states[module.name] = conf_default()

	for module in modules:
		module.state_set(current_states[module.name])

	pub_save()
	print("--------------")

def length(Tracks):
	return datetime.fromtimestamp(sum([i.length for i in Tracks])).strftime("%M:%S")

print("Album name: " + new_state["Album"])
print("Found {} Songs".format(len(new_state["Tracks"])))
print("Cover: " + new_state["tags"]["Cover"].path)
print("Video: " + new_state["Video"].path)
print("Album length: " + length(new_state["Tracks"]))
#print("Tags: " + str(new_state["tags"]))

var_cmds = { "cover" : new_state["tags"]["Cover"],
		    "video" : new_state["Video"]
		   }
quits = ["q", "quit", "exit"]
run = True
while run:
	inp = input("PPublish: ~$ ").split( " " )
	cmd = inp[0].lower()
	Found = True
	if len(inp)==1:
		if cmd in quits:
			run = False
		elif cmd == "save":
			pub_save()
		elif cmd == "detect":
			conf_detect(new_state)
		elif cmd == "check":
			for directory in new_state["dirs"]:
				dir_add(new_state, directory)
		elif cmd == "name":
			print(new_state["Album"])
		elif cmd == "ls":
			print("Tracks:")
			for track in new_state["Tracks"]:
				print(str(track.index) + ". " + track.name)
			print()
			print("Monitoring:")
			for directory in new_state["dirs"]:
				print(directory)
		elif cmd == "length":
			print(length(new_state["Tracks"]))
		elif cmd == "rm_all":
			for track in reversed(new_state["Tracks"]):
				track_rm(new_state["Tracks"], track)
		elif cmd == "reorder":
			file = open("order.txt", "w")
			file.write("\n".join([i.name for i in new_state["Tracks"]]))
			file.close()
			print("waiting for editor to close")
			if os.name=="nt":
				process = subprocess.Popen(["start", "/WAIT", "order.txt"], shell=True)
				process.wait()
			else:
				subprocess.call(('xdg-open', "order.txt"))

			print("Reading File!")
			lines = open("order.txt", "r").read().split("\n")
			for index, name in enumerate(lines):
				print(str(index+1)+". "+ name)
				track = getTrackByName(new_state["Tracks"], name)
				if track == None:
					print("[ERROR] Track could not be found \""+name+"\"")
				else:
					track.index=index+1
			file.close()
			os.remove("order.txt")
			Tracks_sort(new_state["Tracks"])

		elif cmd == "all":
			for module in modules:
				module_run(current_states[module.name], new_state, module)
		else:
			Found=False
			for module in modules:
				if cmd == module.name:
					module_run(current_states[module.name], new_state, module)
					Found=True
					break

			for key in var_cmds:
				if cmd == key:
					print(var_cmds[key])
					Found=True
					break
	elif len(inp)>1:
		arg = " ".join(inp[1:])
		if cmd == "add":
			track_add(new_state["Tracks"], arg)
		elif cmd == "add_dir":
			dir_add(new_state, arg)
		elif cmd == "add_all":
			dir_add(new_state, arg, False)
		elif cmd == "rm_dir":
			dir_rm(new_state, arg)
		elif cmd == "rm":
			track_rmn(new_state["Tracks"], arg)
		elif cmd == "rmi":
			track_rmi(new_state["Tracks"], arg)
		elif cmd == "name":
			setName(new_state, arg)
		elif cmd == "reset":
			args = arg.split(" ")
			for module in modules:
				if module.name in args:
					Reset(module)
					args.remove(module.name)

			for i in args:
				print("Unknown module \""+i+"\"")
		else:
			Found=False
			for key in var_cmds:
				if cmd == key:
					var_cmds[key] = arg
					Found=True
					break

	if not Found:
			print("Unknown command!")

	pub_save()
pub_save()

