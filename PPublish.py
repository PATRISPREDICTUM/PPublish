#!/usr/bin/env python3
import os
import subprocess
import time
import datetime
import copy
import hashlib
import pickle
import re
import audioread

current_states = {}
new_state = {}
save = {}

def join(a, b):
	return os.path.join(a, b).replace("\\", "/")

def realpath(path):
	prefix=""
	if os.name=="nt":
		prefix="\\\\?\\"
		path.replace("/","\\")
	return prefix+os.path.realpath(path)

def getFile(path):
	return os.path.basename(path)

def getNameStart(string):
	match = re.search('[a-zA-Z0-9]{2}[^). ]+', string)
	if match==None:
		return 0
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
			while (chunk := f.read(8192)):
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
		file = getFile(self.path)

		# get Name begining
		start=getNameStart(file)
		if start==None:
			return "Unknown"
		end=file.rfind(".")

		# get name end
		return file[start:end]

	def getlength(self):
		try:
			return audioread.audio_open(self.path).duration
		except:
			self.valid=False
	def __eq__(self, Other):
		if type(Other)==type(self):
			return self.md5==Other.md5
		return False
	def __str__(self):
		return self.name

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
	def __init__(self, old_md5, new_md5):
		self.md5 = old_md5
		self.new = new_md5

	def apply(self, state):
		if (track := getTrackByMD5(state["Tracks"], self.md5)) == None:
			print("[ERROR] Could not find Track in state hash: "+self.org)
			return True
		print(track)
		track.md5=self.new
		return False

class LengthChange:
	def __init__(self, md5, length):
		self.md5 = md5
		self.length=length

	def apply(self, state):
		if (track := getTrackByMD5(state["Tracks"], self.md5)) == None:
			print("[ERROR] Could not find Track in state hash: "+self.org)
			return True
		track.length=self.length

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

class ChangeRecTime:
	def __init__(self, new_time):
		self.new_time=new_time
	def apply(self, state):
		state["rec_time"]=self.new_time
		return False

class UpdateVideo:
	def __init__(self, File):
		self.file=File
	def apply(self, state):
		state["Video"]=self.file
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


def getTrackAttribute(Tracks, lambda_func):
	same = [t for t in Tracks if lambda_func(t)]
	if len(same)==0:
		return None
	if len(same)>1:
		print("[WARNING] Duplicate Tracks found!")
		print([i.name for i in same])
	return same[0]

def getTrackByMD5(Tracks, md5):
	return getTrackAttribute(Tracks, lambda t: t.md5==md5)

def getTrackByName(Tracks, name):
	return getTrackAttribute(Tracks, lambda t: t.name==name)

def getTrackByPath(Tracks, path):
	return getTrackAttribute(Tracks, lambda t: t.path==path)

audio_fmt = ["mp3", "wav", "wma", "flac"]
image_fmt = ["png", "bmp", "jpg", "tiff"]
video_fmt = ["avi", "mp4", "flv", "mkv"]

fmts = audio_fmt+image_fmt+video_fmt


def track_add(state, path):

	if not path.count("/"):
		path = join(os.curdir, path)

	reserved_tracks =[]
	for module in modules:
		if module.state:
			reserved_tracks+=module.state["reserved"]

	for i,rt in enumerate(reserved_tracks):
		if not rt.count("/"):
			reserved_tracks[i] = join(os.curdir, rt)
	if path in reserved_tracks:
		print("skipped reserved track" + path)
		return

	if not path.split(".")[-1] in audio_fmt:
		print(path +" is not an audio file!")
		return path + " is not a audio file!"

	if path in state["removed"]:
		state["removed"].remove(path)

	track = Track(path, len(state["Tracks"])+1)
	if not track.valid:
		print("failed to read audio: "+path)
		invalidate = getTrackByPath(state["Tracks"], path)
		if invalidate:
			print("removing track " +invalidate.name)
			state["Tracks"].remove(invalidate)
		return "Invalid audio"

	dup = getTrackByMD5(state["Tracks"], track.md5)
	twin = getTrackByName(state["Tracks"], track.name)
	if dup:
		if dup.path!=track.path:
			print("sub" + dup.path + " ->" + track.path)
			dup.move(path)
	elif twin:
		print("sub " + twin.path + " hash!")
		twin.md5=track.md5
	else:
		print("Loading Track "+track.path)
		state["Tracks"].append(track)

def track_rm(state, track, blacklist=True):
	index= track.index
	print("Removed "+track.name)
	if not track.path in state["removed"] and blacklist:
		state["removed"].append(track.path)
	state["Tracks"].remove(track)
	for track in state["Tracks"]:
		if track.index>index:
			track.index-=1

def track_rmn(state, name):
	track = getTrackByName(state["Tracks"], name)
	if track == None:
		print("[ERROR] Could not find Track \""+name+"\"")
		return "Track not found"
	track_rm(state, track)

def track_rmi(state, index):
	try:
		num = int(index)
	except:
		print(index + " is not a valid index")
		return
	tracks = [i for i in state["Tracks"] if i.index==num]
	for track in tracks:
		track_rm(state, track)

def Tracks_sort(Tracks):
	Tracks.sort(key=lambda x: x.index)

def Tracks_length(Tracks):
	return sum([i.length for i in Tracks])

def Time_str(seconds):
	return str(datetime.timedelta(seconds =int(seconds)))

def dir_prep(directory):
	directory=directory.strip().replace("\\","/")

	if len(directory)==0:
		directory="."

	if directory[-1]!="/":
		directory+="/"
	return directory

def dir_add(state, save, directory):

	directory = dir_prep(directory)
	if not directory in state["dirs"] and save:
		state["dirs"].append(directory)

	# Get all songs in directory
	for f in os.listdir(realpath(directory)):
		path = directory+f
		if os.path.isfile(path) and f.split(".")[-1] in audio_fmt and (not path in state["removed"] or not save):
			track_add(state, path)

def dir_rm(state, directory):

	directory = dir_prep(directory)
	if directory in state["dirs"]:
		state["dirs"].remove(directory)

	# Get all songs in directory
	for track in reversed(state["Tracks"]):
		if track.path.startswith(directory):
			track_rm(state, track, False)



def dir_relevant(path):
	files = []
	for file in os.listdir(realpath(path)):
		if file.split(".")[-1] in fmts:
			files.append(file)
	return files

def getName():
	folder = getFile(os.getcwd())
	start = getNameStart(folder)
	return folder[start:]

def getCover():
	tmp = [f for f in os.listdir() if len(f.split("."))==2]
	for file in tmp:
		l = file.lower().split(".")
		if l[0]=="cover" and l[1] in image_fmt:
			return File(file)

def getVideo():
	tmp = [f for f in os.listdir() if len(f.split("."))==2]
	for file in tmp:
		l = file.lower().split(".")
		if l[0].startswith("vid") and l[1] in video_fmt:
			return File(file)
	return getCover()

default_paths = { "mp3_path" : "",
				  "wav_path" : " HQ",
				  "video_path" : ".mp4",
				  "full_path" : ".wav"
				  }

def setName(conf, name):
	paths = [i for i in conf if i.endswith("_path")]
	for i in paths:
		if not len(conf[i]):
			if i in default_paths:
				suffix=default_paths[i]
			else:
				suffix=" "+i.split("_")[0]
			conf[i] = name + suffix

		elif conf[i].startswith(conf["Album"]) and len(conf["Album"]):
			conf[i] = conf[i].replace(conf["Album"], name)

	conf["Album"] = name

def conf_detect(conf):
	dir_add(conf, True, os.curdir)
	#album name
	setName(conf, getName())
	conf["tags"]["Cover"]  = getCover()
	conf["Video"] = getVideo()
	print("Album name: " + new_state["Album"])
	print("Found {} Songs".format(len(conf["Tracks"])))
	if conf["tags"]["Cover"]:
		print("Cover: " + conf["tags"]["Cover"].path)
	if conf["Video"]:
		print("Video: " + conf["Video"].path)
	print("Album length: " + Time_str(Tracks_length(conf["Tracks"])))

def conf_check(conf):
	# check monitored directories
	print("Check")
	for directory in conf["dirs"]:
		dir_add(conf, True, directory)

	# check track validities
	for track in conf["Tracks"]:
		track.load()
		if not track.valid:
			print(track.name + " became invalid")
			track_rm(conf, track, False)


def Rename(old_name, new_name):
	changed=False
	while not changed:
		try:
			os.rename(realpath(old_name), realpath(new_name))
			changed=True
		except PermissionError:
			print(old_name+" in use please resolve")
			time.sleep(1)
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

def Junkify(path):
	try:
		os.mkdir("junk")
	except:
		pass

	file = getFile(path)
	suffix = ""
	name = file
	if file.count("."):
		name = ".".join(file.split(".")[:-1])
		suffix = "."+file.split(".")[-1]

	i=0
	while name+"_"+str(i)+suffix in os.listdir("junk"):
		i+=1
	Rename(path, "junk/"+name+"_"+str(i)+suffix)


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
	module.clear()
	conf_default(module.state)

# specific ffmpeg wrapper

class ffmpeg_input:
	def __init__(self):
		self.specifiers=[] # stream_loop etc
		self.streams = [] # paths to streams
		self.map = [] # a and v
		self.filters = [] # optional additional filters

class ffmpeg_output:
	def __init__(self):
		self.attributes = []
		self.path = None

class ffmpeg:
	def __init__(self):
		self.inputs = []
		self.output = None
		self.id_current=None

	def id_next(self):
		if self.id_current==None:
			self.id_current=0
			return self.id_current

		self.id_current+=1
		return self.id_current

	def run(self):
		if not len(self.inputs) or not self.output:
			return True
		cmd = "ffmpeg"
		stream_offset=0

		# get stream as input
		for i in self.inputs:
			for s in i.streams:
				for spec in i.specifiers:
					cmd+= " -"+spec
				cmd+= " -i \""+ realpath(s) +"\""

		# write filters
		filters = []
		for i in self.inputs:
			stream_count = len(i.streams)
			# if only one stream and so filters skip filters for stream copy support
			if stream_count==1 and not len(i.filters):
				i.out = str(stream_offset)
			else:
				c_filter=""
				for s in range(stream_count):
					c_filter+=f"[{s+stream_offset}:0]"
				c_filter+=f"concat=n={stream_count}:a={int('a' in i.map)}:v={int('v' in i.map)}[{self.id_next()}]"

				for f_filter in i.filters:
					c_filter+=f",[{self.id_current}]{f_filter}[{self.id_next()}]"
				filters.append(c_filter)
				# set final output
				i.out = "["+str(self.id_current)+"]"
			stream_offset+=stream_count


		if len(filters):
			cmd+= " -filter_complex \""
			cmd+=", ".join(filters)
			cmd+="\""

		# perform output mappings
		for i in self.inputs:
			for stream_map in i.map:
				cmd+= f" -map \"{i.out}:{stream_map}\""

		for attri in self.output.attributes:
			cmd += " -" +attri

		cmd += " \""+realpath(self.output.path) +"\" -y"
		print("------DEBUG-------")
		print(cmd)
		print("------------------")
		os.system(cmd)

class module:
	def __init__(self):
		self.name = type(self).__name__
		self.state=None

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
	def handle(self, task, update):
		pass
	def __str__(self):
		return self.name

	def description(self):
		return ""

	def getMd5(self, md5):
		if (track := getTrackByMD5(self.Tracks, md5)) == None:
			print("[ERROR] Could not find Track \""+update.track.name+"\"")
		return track


class module_folder(module):

	def delete(self, track):
		path = join(self.path,self.getName(track.index,track.name))
		if path in self.state["reserved"]:
			self.state["reserved"].remove(path)
		Delete(path)

	def clear(self):
		for track in self.Tracks:
			self.delete(track)
		self.Tracks.clear()
		dir_Delete(self.path)

	def verify(self, new_state):
		if not os.path.exists(self.path):
			Reset(self)
		else:
			for track in reversed(self.Tracks):
				if not self.getName(track.index, track.name) in os.listdir(realpath(self.path)):
					self.Tracks.remove(track)
					path = join(self.path,self.getName(track.index,track.name))
					if path in self.state["reserved"]:
						self.state["reserved"].remove(path)

			track_names = [self.getName(t.index, t.name) for t in self.Tracks]
			for file in os.listdir(realpath(self.path)):
				if not file in track_names:
					Junkify(join(self.path, file))

	def Rename(self, old_name, new_name):
			Rename(join(self.path,old_name), join(self.path, new_name))
			if old_name in self.state["reserved"]:
				self.state["reserved"].remove(old_name)
				self.state["reserved"].append(new_name)

	def handleRename(self, update):
		track = getTrackByMD5(self.Tracks, update.md5)
		if track == None:
			print("[ERROR] Could not find Track in state hash: "+update.md5)
			return True

		old_name = self.getName(track.index,track.name)
		if not old_name in os.listdir(realpath(self.path)):
			print("[ERROR] Could not find Track in folder \""+track.path+"\"")
			return True

		new_path = self.getName(track.index, update.new_path)
		self.Rename(old_name, new_path)

	def handleReorder(self, update):
		if not (track := self.getMd5(update.md5)):
			return True
		print(track)

		old_name = self.getName(track.index,track.name)
		if not old_name in os.listdir(realpath(self.path)):
			print("[ERROR] Could not find Track in folder \""+old_name+"\"")
			return True

		new_name = self.getName(update.index,track.name)
		self.Rename(old_name, new_name)

	def handleInit(self, update):
		try:
			os.mkdir(update.path)
		except:
			for i in os.listdir(realpath(update.path)):
				Junkify(join(update.path,i))

	def handleChangePath(self, update):
		if update.module==self.name:
			return Rename(self.path, update.path)

	def Render_extend(self, inst):
		pass

	def Render(self, track):
		ffmpeg_inst = ffmpeg()

		f_input = ffmpeg_input()
		f_input.streams.append(track.path)
		f_input.map=["a"]

		output=self.getOutput(track)
		output.path=join(self.path, self.getName(track.index, track.name))

		ffmpeg_inst.inputs.append(f_input)
		ffmpeg_inst.output = output

		# add user extentions
		self.Render_extend(ffmpeg_inst)

		ffmpeg_inst.run()
		if not output.path in self.state["reserved"]:
			self.state["reserved"].append(output.path)

class mp3(module_folder):

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Cover = self.state["tags"]["Cover"]
		self.tags = self.state["tags"]

	def getOutput(self, track):
		ffmpeg_out = ffmpeg_output()
		ffmpeg_output.attributes = ["id3v2_version 3",
									f"metadata title=\"{track.name}\"",
									f"metadata track=\"{track.index}\"",
									f"metadata album_artist=\"{self.tags['Artist']}\"",
									f"metadata album=\"{self.Album}\"",
									f"metadata genre=\"{self.tags['Genre']}\"",
									f"metadata artist=\"{','.join(self.tags['feat'])}\""]

		return ffmpeg_output

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

	def description(self):
		return "Creates tagged mp3 files of file with integraded Album Cover"

	def handle(self, task, update):
		if task == "RenameTrack":
			if (res := self.handleRename(update)):
				return res
			track = getTrackByMD5(self.Tracks, update.md5)
			self.retag_track(track)

		elif task == "ChangePath":
			self.handleChangePath(update)

		elif task == "NewTrack":
			self.rerender_track(update.track)

		elif task == "UpdateTrack":
			if not (track := self.getMd5(update.md5)):
				return True

			self.rerender_track(track)

		elif task == "DeleteTrack":
			self.delete(update.track)

		elif task == "Updatemp3tags":
			for track in self.Tracks:
				self.retag_track(track)

		elif task == "Reorder":
			if (res := self.handleReorder(update)):
				return res

			track = getTrackByMD5(self.Tracks, update.md5)
			self.retag_track(track)

		elif task == "Initilize":
			self.handleInit(update)

		elif task == "Clear":
			clear()

		return False

	def getName(self, index, name):
		return str(index)+". "+name+".mp3"


	def ReTag(self, track):
		# rename old track
		name=self.getName(track.index,track.name)
		tmp_path = join(self.path, "tmp_"+name)
		if not name in os.listdir(realpath(self.path)):
			print("[ERROR] could not find Track \""+track.name+"\"")
			return True
		if Rename(join(self.path, name), tmp_path):
			return True

		ffmpeg_inst = ffmpeg()

		f_input = ffmpeg_input()
		f_input.streams.append(tmp_path)
		f_input.map=["a"]

		output=self.getOutput(track)
		output.attributes.append("c:a copy")
		output.path=join(self.path, self.getName(track.index, track.name))

		ffmpeg_inst.inputs.append(f_input)
		ffmpeg_inst.output = output

		self.Render_add_cover(ffmpeg_inst)

		ffmpeg_inst.run()

		# delete old track
		Delete(tmp_path)

	def Render_add_cover(self, inst):
		# add image stream if cover exists
		print(self.state["tags"])
		if self.Cover:
			print(self.Cover.valid)
			if self.Cover.valid:
				cover = ffmpeg_input()
				cover.streams.append(self.Cover.path)
				cover.map=["v"]
				inst.inputs.append(cover)

	def Render_extend(self, inst):
		self.Render_add_cover(inst)

		# mp3 codec
		inst.output.attributes+=["b:a 320k", "acodec libmp3lame"]


class wav(module_folder):

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Cover = self.state["tags"]["Cover"]
		self.tags = self.state["tags"]

	def description(self):
		return "Creates high quality Wav output of album"

	def handle(self, task, update):
		if task == "RenameTrack":
			self.handleRename(update)

		elif task == "ChangePath":
			self.handleChangePath(update)

		elif task == "NewTrack":
			self.Render(update.track)

		elif task == "UpdateTrack":
			if not (track := self.getMd5(update.md5)):
				return True
			self.Render(track)

		elif task == "DeleteTrack":
			self.delete(update.track)

		elif task == "Reorder":
			track = getTrackByMD5(self.Tracks, update.md5)
			if track == None:
				print("[ERROR] Could not find track! hash: "+update.md5)
				return True

			old_name = self.getName(track.index,track.name)
			if not old_name in os.listdir(realpath(self.path)):
				print("[ERROR] Could not find Track in folder \""+old_name+"\"")
				return True

			track.index=update.index
			new_name = self.getName(track.index,track.name)
			Rename(join(self.path,old_name), join(self.path, new_name))

		elif task == "Initilize":
			try:
				os.mkdir(update.path)
			except:
				for i in os.listdir(realpath(update.path)):
					Junkify(join(update.path,i))

		elif task == "Clear":
			clear()


		return False

	def getName(self, index, name):
		return str(index)+". "+name+".wav"

	def getOutput(self, track):
		out = ffmpeg_output()
		out.attributes=["ar 44100", "ac 2"]
		return out

class module_hash(module):

	def save(self):
		self.state["output"]=File(realpath(self.path))
		if not self.state["output"].valid:
			print(self.name + " failed to execute")
			Reset(self)
		else:
			print("New Hash: " + self.state["output"].md5)

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

class video(module_hash):
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
		if not self.Video:
			msg = "Video module needs video or cover"
			print(msg)
			return msg
		if self.job:
			res = self.jobs[self.job-1]()
			self.save()

			return res
		return False

	def description(self):
		return "Creates an Album video for Youtube, uses either the Cover as a still or a video if found"

	def handle(self, task, update):

		if task == "ChangePath":
			if update.module==self.name:
				Rename(self.path, update.path)

		elif task == "DeleteTrack" or task == "Reorder" or task == "UpdateTrack" or task == "NewTrack":
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

	def getOutput(self, inst):
		output = ffmpeg_output()
		output.path = self.path
		inst.output=output

	def extend_video(self, inst):
		if self.Video.valid:
			cover = ffmpeg_input()
			cover.streams = [ self.Video.path ]
			cover.map=["v"]
			inst.output.attributes.append("shortest") # doesn't work; ffmpeg bug
			# Workaround

			inst.output.attributes.append("t " + Time_str(Tracks_length(self.Tracks)))


			if self.Video.path.split(".")[-1] in video_fmt:
				cover.specifiers=["stream_loop -1"]
				#inst.output.attributes.append("c:v copy") # massive speed boost, but enormous file size
			else:
				cover.specifiers=["loop 1"]
				inst.output.attributes.append("pix_fmt yuv420p")

			# fix ffmpeg odd dimension error https://stackoverflow.com/questions/20847674/ffmpeg-libx264-height-not-divisible-by-2
			cover.filters.append("pad=ceil(iw/2)*2:ceil(ih/2)*2")
			inst.inputs.append(cover)

	def extend_audio(self, inst):
		audio = ffmpeg_input()
		Tracks_sort(self.Tracks)
		audio.streams=[t.path for t in self.Tracks]
		audio.map = ["a"]
		inst.output.attributes+=["b:a 320k", "acodec libmp3lame"]
		inst.inputs.append(audio)

	def extend_reuse(self, inst, stream):
		reuse = ffmpeg_input()
		if Rename(self.path, "tmp_"+self.path):
			return True
		reuse.streams = ["tmp_"+self.path]
		reuse.map=[stream]
		inst.output.attributes.append(f"c:{stream} copy")
		inst.inputs.append(reuse)


	def Render(self):
		inst = ffmpeg()
		self.getOutput(inst)
		self.extend_video(inst)
		self.extend_audio(inst)
		inst.run()

	def Render_audio(self):
		inst = ffmpeg()
		self.getOutput(inst)
		if self.extend_reuse(inst, "v"):
			return True
		self.extend_audio(inst)
		inst.run()
		Delete("tmp_"+self.path)

	def Render_video(self):
		inst = ffmpeg()
		self.getOutput(inst)
		if self.extend_reuse(inst, "a"):
			return True
		self.extend_video(inst)
		inst.run()
		Delete("tmp_"+self.path)

	def clear(self):
		self.Tracks.clear()
		Delete(self.path)
		Delete("tmp_"+self.path)

class description(module):

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Artist = self.state["tags"]["Artist"]
		self.Album = self.state["Album"]

	def start(self):
		self.rerender=False

	def end(self):
		if self.rerender:
			print("Rerendering!")
			self.output()

	def verify(self, new_state):
		pass

	def description(self):
		return "Creates a description for Youtube with timestamps for the Tracks"

	def handle(self, task, update):
		if task == "ChangePath":
			if update.module==self.name:
				Rename(self.path, update.path)
		elif task == "NewTrack" or task == "LengthChange" or task == "DeleteTrack" or task == "Reorder":
			self.rerender=True


	def output(self):
		print(self.path)
		i=0
		timestamps = []
		for track in self.Tracks:
			timestamps.append(str(datetime.timedelta(seconds=int(i)))+" "+track.name)
			i+=track.length

		string = "\n".join(timestamps)
		file = open(self.path, "w")
		file.write(self.Artist+"s new Album " + self.Album + " is now on Youtube!!\nEnjoy our latest Tracks UwU\n\nTimestamps:\n")
		file.write(string)
		file.close()

	def clear(self):
		self.Tracks.clear()
		Delete(self.path)

class full(module_hash):

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.Video = self.state["Video"]


	def start(self):
		self.rerender =False

	def end(self):
		if self.rerender:
			self.render()
			self.save()
			if not self.path in self.state["reserved"]:
				self.state["reserved"].append(self.path)
		return False

	def description(self):
		return "Combines all Tracks into one continuous audio stream"

	def handle(self, task, update):
		if task == "ChangePath":
			if update.module==self.name:
				Rename(self.path, update.path)
		elif task == "NewTrack" or task == "UpdateTrack" or task == "DeleteTrack" or task == "Reorder":
			self.rerender=True

		return False

	def render(self):
		audio = ffmpeg_input()
		audio.streams = [i.path for i in self.Tracks]
		audio.map=["a"]
		inst = ffmpeg()
		inst.inputs=[audio]
		out = ffmpeg_output()
		out.path = self.path
		inst.output=out
		inst.run()

	def clear(self):
		self.Tracks.clear()
		Delete(self.path)
		if self.path in self.state["reserved"]:
			self.state["reserved"].remove(self.path)

class tl_sketch(module):

	def load(self,):
		super().load()
		self.path = self.state[self.name+"_path"]
		self.sketch_path = join(self.path, getFile(self.path)+".ino")
		self.Video = self.state["Video"]
		self.rec_time = self.state["rec_time"]

	def start(self):
		self.job = 0

	def end(self):
		if self.job:
			self.Render()

		return False

	def description(self):
		return "Creates an Arduino Sketch to display track info for a timelapse video"

	def handle(self, task, update):

		if task == "ChangePath":
			if update.module==self.name:
				Rename(self.path, update.path)

		elif task == "DeleteTrack" or task == "Reorder" or task == "UpdateTrack" or task == "NewTrack" or task == "RenameTrack" or task == "ChangeRecTime":
			self.job=1

		elif task == "Clear":
			clear()

		return False


	def Render(self):
		print(self.rec_time/Tracks_length(self.Tracks))
		print(str(self.rec_time) +":"+ str(Tracks_length(self.Tracks)))
		try:
			os.mkdir(self.path)
		except Exception as e:
			print(e)

		file = open(self.sketch_path, "w")
		file.write("""#include <Wire.h> 
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27,20,4);

#define FPS 5

#define TIME_MULT """+ str(self.rec_time/Tracks_length(self.Tracks)) +"""
#define SCROLL_TIME 2

struct Track
{
  const char *title;
  double time;
};


struct Track tracks[] = {
	{"Starting in ...", 5.0/TIME_MULT},
""")
		for track in self.Tracks:
			file.write("	{\""+track.name+"\", "+ str(track.length) + "},\n")

		file.write("""
};
const uint32_t tracks_length = sizeof(tracks)/sizeof(*tracks);

void setup()
{          
  // init LCD
  lcd.init();
  lcd.backlight();


  uint32_t title_offset=0,
           tracks_index=0;
           
  uint8_t ;
  double time=0,
  		 time_last=0,
         length=tracks[0].time,
         last_scroll=0,
         last_p=0,
         percentage;
  size_t len;
  unsigned long start, last;
  
  lcd.print(tracks[tracks_index].title);
  len = strlen(tracks[tracks_index].title);

  int32_t wait;

  start=millis();
  last=start;
  while(tracks_index < tracks_length)
  {
    percentage=(time-time_last)*18/tracks[tracks_index].time;
    if(percentage<18){

      lcd.setCursor((uint8_t)percentage+1,1);
      if(percentage<17)
        lcd.print((uint8_t)((percentage-(uint8_t)percentage)*10));

      for(int i=last_p; i<(uint8_t)percentage; i++)
      {
        lcd.setCursor(i-1,1);
        lcd.print((char)255);
      }

      last_p=percentage;
    }

    if(time-last_scroll>=SCROLL_TIME && len>16){
      last_scroll=time;

      title_offset=++title_offset%len;
      lcd.setCursor(0,0);
      int i;
      for(i=0; i<len-title_offset && i<16; i++)
        lcd.print(tracks[tracks_index].title[i+title_offset]);
      if(i++<16)
        lcd.print(" ");
      if(i++<16)
        lcd.print(" ");
      for(int x=0; i+x<16; x++)
        lcd.print(tracks[tracks_index].title[x]);
    }
    
    // wait frame
    wait=1000.0/FPS-millis()+last;
    if(wait>0)
      delay(wait);
    last=millis();
    time=(millis()-start)/1000.0/TIME_MULT;
    
    // if track over -> goto next
    if(time-time_last>tracks[tracks_index].time){
      time_last+=tracks[tracks_index].time;
      last_scroll=time;
      title_offset=0;
      length=tracks[++tracks_index].time;
      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print(tracks[tracks_index].title);
      len = strlen(tracks[tracks_index].title);
    }
  }
}

void loop(){};""")
		file.close()


	def clear(self):
		self.Tracks.clear()
		Delete(self.sketch_path)
		dir_Delete(self.path)



modules = [ mp3(), wav(), full(), video(), description(), tl_sketch() ]

def conf_default(conf):
	conf.clear()

	conf["Tracks"] = []
	conf["Album"] = ""
	conf["dirs"] = []
	conf["removed"] = []
	conf["reserved"] = []

	#mp3 tags
	conf["tags"]={}
	conf["tags"]["Artist"] = "PATRIS PREDICTUM"
	conf["tags"]["Genre"]  = "dominationdead"
	conf["tags"]["feat"]   = []
	conf["tags"]["Cover"]  = None
	conf["Video"] = None
	conf["rec_time"]=12*60*60 # 12 hours

	# module conf
	for module in modules:
		conf[module.name+"_path"] = ""

	conf["description_path"] = "Description.txt"
	conf["tl_sketch_path"] = "tl_sketch"

	return conf

def getDiff(old_state, new_state):
	diff = []
	if old_state["tags"]!=new_state["tags"]:
		diff.append(Updatemp3tags(new_state["tags"]))

	if old_state["Album"]!=new_state["Album"]:
		diff.append(RenameAlbum(new_state["Album"]))
		diff.append(Updatemp3tags(new_state["tags"]))

	if old_state["rec_time"]!=new_state["rec_time"]:
		diff.append(ChangeRecTime(new_state["rec_time"]))

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
				if track==new_track and track.name!=new_track.name:
					diff.append(RenameTrack(track.md5, new_track.name))

				if track == new_track or track.name==new_track.name:
					if track.index!=new_track.index:
						diff.append(Reorder(track.md5, new_track.index))
					if track.length!=new_track.length:
						diff.append(LengthChange(track.md5, new_track.length))


	for track in new_state["Tracks"]:
		if not track in old_state["Tracks"]:
			Found=False
			for old_track in old_state["Tracks"]:
				if track.name==old_track.name:
					diff.append(UpdateTrack(old_track.md5, new_track.md5))
					Found=True
					break
			if not Found:
				diff.append(NewTrack(track))
	return diff

def module_run(current_state, new_state, module):
	module.verify(new_state) # veriy Environment before execution
	module.load()
	module.start() # signal start of transactions
	# if no path set initilize
	if not len(module.path):
		init = Initilize(new_state[module.name+"_path"], module.name)
		task = type(init).__name__
		module.handle(task, init)
		init.apply(current_state)
	diffs = getDiff(current_state, new_state)
	# pass each change to module handler
	for diff in diffs:
		task = type(diff).__name__
		print(module.name + " -> " + task)
		module.load()
		if module.handle(task, diff):
			break
		diff.apply(current_state) # apply difference
	module.load()
	return module.end()


savefile = ".ppub"
def pub_save():
	save["current_states"]=current_states
	save["new_state"]=new_state
	pickle.dump(save, open(savefile, "wb"))

if savefile in os.listdir():
	print("Loading savefile!")
	save = pickle.load(open(savefile, "rb"))

	current_states = save["current_states"]
	new_state = save["new_state"]


	for module in modules:
		if not module.name in current_states:
			print("New Module " + module.name)
			current_states[module.name] = conf_default({})
			new_state[module.name+"_path"]=""
		module.state_set(current_states[module.name])


	conf_check(new_state)

else:
	print("---Analyzing Environment---")
	new_state = conf_default({})

	conf_detect(new_state)
	for module in modules:
		current_states[module.name] = conf_default({})
		module.state_set(current_states[module.name])

	pub_save()
	print("--------------")

#print("Tags: " + str(new_state["tags"]))

class Var_get_set:
	def __init__(self, field, key):
		self.field = field
		self.key = key
	def set(self, val):
		self.field[self.key] = val

	def get(self):
		return self.field[self.key]

class Var_Time:
	def __init__(self, field, key):
		self.field = field
		self.key = key
	def set(self, val):
		while True:
			try:
				s = time.strptime(val, "%H:%M:%S")
				d = datetime.timedelta(hours=s.tm_hour, minutes=s.tm_min, seconds=s.tm_sec).total_seconds()
				print(str(d) + " sec")
			except Exception as e:
				print(e)
				print("Please enter correct time in HH:MM:SS format")
				continue
			break

		self.field[self.key]=d

	def get(self):
		return Time_str(self.field[self.key])

class Var_File(Var_get_set):
	def set(self, val):
		file = File(val)
		if not file.valid:
			print("File invalid!")
			return
		self.field[self.key] = file

	def get(self):
		if self.field[self.key]:
			return self.field[self.key].path
		return "Not Found!"

class Var_Name(Var_get_set):
	def set(self, val):
		setName(val)

# set simple fiels
var_set = { "Cover"   : Var_File(new_state["tags"], "Cover"),
			"Video"  : Var_File(new_state, "Video"),
			"Artist" : Var_get_set(new_state["tags"], "Artist"),
			"Genre"  : Var_get_set(new_state["tags"], "Genre"),
			"Album"  :	Var_Name(new_state, "Album"),
			"rec_time" : Var_Time(new_state, "rec_time")
		   }
#append paths to var_set
for module in modules:
	var_set[module.name+"_path"]=Var_get_set(new_state,module.name+"_path")

class cmd:
	def run(self, args):
		pass

	def description(self):
		return "Not Documented"

	def usage(self):
		return "No Usage"

class cmd_unary(cmd):
	def usage(self):
		return self.id()
	def _run(self):
		pass

	def run(self, args):
		if not len(args):
			return self._run()
		else:
			return self.id() + " takes no args"

class cmd_save(cmd_unary):
	def _run(self):
		pub_save()
		pass

	def description(self):
		return "Saves current states to .ppub"

	def id(self):
		return "save"
class cmd_detect(cmd_unary):
	def _run(self):
		conf_detect(new_state)
		for directory in new_state["dirs"]:
			dir_add(new_state, True, directory)

	def description(self):
		return "Detects Environment eg.\ncheck monitored directories for Tracks,\nGuess Album from Folder name\nSearch Cover and Video files"

	def id(self):
		return "detect"

class cmd_check(cmd_unary):
	def _run(self):
		conf_check(new_state)

	def description(self):
		return "Checks all monitored directories for new Tracks"

	def id(self):
		return "check"

class cmd_set_vars(cmd):
	def __init__(self, var_set):
		self.var_set = var_set

	def run(self, args):
		arg = " ".join(args[1:])
		if len(args)>1:
			found = False
			for var in self.var_set:
				if var.lower()==args[0].lower():
					found = True
					self.var_set[var].set(arg)

					print(var+" is now "+self.var_set[var].get())
					break
			if not found:
				return "Unknown field \""+args[0]+"\""

		else:
			return "not enough args"

	def description(self):
		return "sets value of [field]\nfield is caseinsensitive\n\nAvailable fields:\n"+"\n".join(self.var_set)

	def id(self):
		return "set"

	def usage(self):
		return "set [field] [value]"

class cmd_get_vars(cmd):
	def __init__(self, var_set):
		self.var_set = var_set

	def run(self, args):
		if len(args)==1:
			found = False
			for var in self.var_set:
				if var.lower()==args[0].lower():
					found = True
					print(var+": "+self.var_set[var].get())
					break
			if not found:
				return "Unknown field \""+args[0]+"\""
		else:
			return "Too many args"

	def description(self):
		return "prints current value of [field]\nfield is caseinsensitive\n\nAvailable fields:\n"+"\n".join(self.var_set)

	def id(self):
		return "get"

	def usage(self):
		return "get [field]"

class cmd_ls(cmd):
	def run(self, args):
		arg = " ".join(args)
		files = dir_relevant(arg)

		for i, file in enumerate(files):
			print(i+1, file)

	def description(self):
		return "Lists all relevant files in [dir]\nTracks could be imported using addi"

	def usage(self):
		return "ls [dir]"

	def id(self):
		return "ls_dir"

class cmd_fam_ls(cmd_unary):
	def __init__(self, name, List, desc = "all elements"):
		self.List =List
		self.name = name
		self.desc = desc

	def _run(self):
		for i,e in enumerate(self.List):
			print(f"{i+1:02}. "+ str(e))

	def id(self):
		return self.name

	def description(self):
		return "Lists " + self.desc

class cmd_length(cmd_unary):
	def _run(self):
		print(Time_str(Tracks_length(new_state["Tracks"])))

	def id(self):
		return "length"

	def description(self):
		return "Prints length of album eg. all currently loaded Tracks"

class cmd_rm_all(cmd_unary):
	def _run(self):
		for track in reversed(new_state["Tracks"]):
			track_rm(new_state, track, False)

	def description(self):
		return "Clears Tracklist"

	def id(self):
		return "rm_all"

class cmd_reorder(cmd_unary):
	def _run(self):
		file = open("order.txt", "w")
		file.write("\n".join([i.name for i in new_state["Tracks"]]))
		file.close()
		print("waiting for editor to close")
		start = datetime.datetime.now()
		if os.name=="nt":
			process = subprocess.Popen(["start", "/WAIT", "order.txt"], shell=True)
			process.wait()
		else:
			cmd = [os.getenv('EDITOR')]
			if not cmd[0]:
				cmd = ["vi","-c" ,"set number"]
			cmd.append("order.txt")
			process = subprocess.Popen(
				cmd)
			process.wait()
		end = datetime.datetime.now()

		if (end-start).total_seconds()<1:
			print("Autodetection failed! Press Enter resume")
			input()

		print("Reading File!")
		lines = open("order.txt", "r").read().split("\n")
		for index, name in enumerate(lines):
			if len(name):
				print(str(index+1)+". "+ name)
				track = getTrackByName(new_state["Tracks"], name)
				if track == None:
					return "Track could not be found \""+name+"\", don't change the names"
				else:
					track.index=index+1
		file.close()
		os.remove("order.txt")
		Tracks_sort(new_state["Tracks"])

	def description(self):
		return "Promts reorder dialouge\nChange the order of the Tracks inside the editor, save, and quit"

	def id(self):
		return "reorder"

class cmd_all(cmd_unary):
	def _run(self):
		for module in modules:
			module_run(current_states[module.name], new_state, module)

	def id(self):
		return "all"

	def description(self):
		return "Run all available modules in sequence"

class cmd_forward_arg(cmd):
	def __init__(self, name, desc, arg, func, args):
		self.func=func
		self.args=args
		self.name=name
		self.desc=desc
		self.arg=arg

	def run(self, args):
		if not len(args):
			return self.name + " requires one argument"
		arg = " ".join(args)
		return self.func(*self.args, arg)

	def description(self):
		return self.desc

	def id(self):
		return self.name

	def usage(self):
		return self.name + " ["+self.arg+"]"

class cmd_reset(cmd):
	def run(self, args):
		global new_state
		for module in modules:
			if module.name in args:
				Reset(module)
				args.remove(module.name)

		if "main" in args:
			new_state=conf_default({})
			args.remove("main")
		if len(args):
			return "Unknown module \""+"\"\nUnknown module \"".join(args)+"\""

	def id(self):
		return "reset"
	def description(self):
		return "resets the states of all listed modules\nModules:\n"+"\n".join([i.name for i in modules])+"\nmain"

	def usage(self):
		return "reset [module...]"

class cmd_addi(cmd):
	def run(self, args):
		if len(args)<2:
			return "Too few args"

		errors = []
		files=dir_relevant(args[0])
		for i in args[1:]:
			index=int(i)-1
			if index<len(files):
				track_add(new_state, join(args[0], files[index]))
			else:
				errors.append(i)
		if len(errors):
			return ", ".join(errors) + " index is out of range"

	def id(self):
		return "addi"

	def description(self):
		return "adds files from [dir] by indecies"

	def usage(self):
		return "addi [path] [index...]"

commands = [cmd_fam_ls("ls", new_state["Tracks"], "all loaded Tracks"), cmd_ls(), cmd_fam_ls("ls_mod", modules, "all available modules"),
			cmd_fam_ls("ls_rm", new_state["removed"], "backlisted tracks\nload track manually to remove track from blacklist"), cmd_fam_ls("ls_mon", new_state["dirs"], "currently monitored directories"),
			cmd_forward_arg("add", "loads new Track from path", "path", track_add, [new_state]), cmd_addi(),
			cmd_forward_arg("add_dir", "adds directory to monitoring list eg. loads all current and future Tracks from this directory", "path", dir_add, [new_state, True]),
			cmd_forward_arg("add_all", "loads all Tracks from directory, but doesn't start monitoring", "path", dir_add, [new_state, False]), cmd_forward_arg("rm", "unloads Track with name", "name", track_rmn, [new_state]),
			cmd_rm_all(), cmd_forward_arg("rmi", "unloads Track with index", "index", track_rmi, [new_state]), cmd_forward_arg("rm_dir", "unloads all tracks from this directory, stops monitoring", "path", dir_rm, [new_state]),
			cmd_reset(),
			cmd_get_vars(var_set), cmd_set_vars(var_set),
			cmd_length(), cmd_reorder(), cmd_all(),
			cmd_save(), cmd_detect(), cmd_check()
			]

quits = ["q", "quit", "exit"]

run = True
while run:
	inp = input("PPublish: ~$ ").strip().split( " " )
	cmd = inp[0].lower()
	if not len(cmd):
		continue
	Found = True
	if cmd in quits:
		run = False
	elif cmd == "help":
		print("Help for PPublish by NoHamster")
		print("Exit with " + ", ".join(quits))
		print("Commands:")
		print("Execute via shell")
		print("---------")
		for cmd in commands:
			print(cmd.id()+":")
			print("\t"+cmd.usage())
			print()
			print("\t"+cmd.description().replace("\n", "\n\t"))
		print("---------")
		print()


		print("Modules:")
		print("can also be called through the shell")
		print("---------")
		for module in modules:
			print(module.name + " - " + module.description())
		print("---------")
		print()

		print("Setting fields:")
		print("View or Change these with 'get' and 'set'")
		print("---------")
		for var in var_set:
			print(var)
		print("---------")
		print()

	else:
		Found=False
		for command in commands:
			if cmd==command.id().lower():
				error = command.run(inp[1:])
				if error:
					print("An error occured while executing command:")
					print("[ERROR] " + command.id() + ": " + str(error))
					print("use 'help' if your unsure of usage")
				Found=True

		if not Found:
			for module in modules:
				if cmd == module.name:
					if (error := module_run(current_states[module.name], new_state, module)):
						print("[ERROR] Module falied to run: " +str(error))
					Found=True
					break

	if not Found:
			print("[ERROR] Unknown command \"" + cmd + "\"")

	pub_save()
pub_save()

