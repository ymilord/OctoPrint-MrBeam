# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


from . import s

import re

class SupportLocationTypes(object):
	NONE = "none"
	TOUCHING_BUILDPLATE = "buildplate"
	EVERYWHERE = "everywhere"

class SupportDualTypes(object):
	BOTH = "both"
	FIRST = "first"
	SECOND = "second"

class SupportTypes(object):
	GRID = "grid"
	LINES = "lines"

class PlatformAdhesionTypes(object):
	NONE = "none"
	BRIM = "brim"
	RAFT = "raft"

class MachineShapeTypes(object):
	SQUARE = "square"
	CIRCULAR = "circular"

class GcodeFlavors(object):
	REPRAP = "reprap"
	REPRAP_VOLUME = "reprap_volume"
	ULTIGCODE = "ultigcode"
	MAKERBOT = "makerbot"
	BFB = "bfb"
	MACH3 = "mach3"


defaults = dict(
	speed=100,
	intensity=100
)


class Profile(object):

	regex_extruder_offset = re.compile("extruder_offset_([xy])(\d)")
	regex_filament_diameter = re.compile("filament_diameter(\d?)")
	regex_print_temperature = re.compile("print_temperature(\d?)")
	regex_strip_comments = re.compile(";.*$", flags=re.MULTILINE)

	@classmethod
	def from_svgtogcode_ini(cls, path):
		import os
		if not os.path.exists(path) or not os.path.isfile(path):
			return None

		import ConfigParser
		config = ConfigParser.ConfigParser()
		try:
			config.read(path)
		except:
			return None

		arrayified_options = ["print_temperature", "filament_diameter", "start.gcode", "end.gcode"]
		translated_options = dict(
			inset0_speed="outer_shell_speed",
			insetx_speed="inner_shell_speed",
			layer0_width_factor="first_layer_width_factor",
			simple_mode="follow_surface",
		)
		translated_options["start.gcode"] = "start_gcode"
		translated_options["end.gcode"] = "end_gcode"
		value_conversions = dict(
			platform_adhesion={
				"None": PlatformAdhesionTypes.NONE,
				"Brim": PlatformAdhesionTypes.BRIM,
				"Raft": PlatformAdhesionTypes.RAFT
			},
			support={
				"None": SupportLocationTypes.NONE,
				"Touching buildplate": SupportLocationTypes.TOUCHING_BUILDPLATE,
				"Everywhere": SupportLocationTypes.EVERYWHERE
			},
			support_type={
				"Lines": SupportTypes.LINES,
				"Grid": SupportTypes.GRID
			},
			support_dual_extrusion={
				"Both": SupportDualTypes.BOTH,
				"First extruder": SupportDualTypes.FIRST,
				"Second extruder": SupportDualTypes.SECOND
			}
		)

		result = dict()
		for section in config.sections():
			if not section in ("profile", "alterations"):
				continue

			for option in config.options(section):
				ignored = False
				key = option

				# try to fetch the value in the correct type
				try:
					value = config.getboolean(section, option)
				except:
					# no boolean, try int
					try:
						value = config.getint(section, option)
					except:
						# no int, try float
						try:
							value = config.getfloat(section, option)
						except:
							# no float, use str
							value = config.get(section, option)
				index = None

				for opt in arrayified_options:
					if key.startswith(opt):
						if key == opt:
							index = 0
						else:
							try:
								# try to convert the target index, e.g. print_temperature2 => print_temperature[1]
								index = int(key[len(opt):]) - 1
							except ValueError:
								# ignore entries for which that fails
								ignored = True
						key = opt
						break
				if ignored:
					continue

				if key in translated_options:
					# if the key has to be translated to a new value, do that now
					key = translated_options[key]

				if key in value_conversions and value in value_conversions[key]:
					value = value_conversions[key][value]

				if index is not None:
					# if we have an array to fill, make sure the target array exists and has the right size
					if not key in result:
						result[key] = []
					if len(result[key]) <= index:
						for n in xrange(index - len(result[key]) + 1):
							result[key].append(None)
					result[key][index] = value
				else:
					# just set the value if there's no array to fill
					result[key] = value

		# merge it with our default settings, the imported profile settings taking precedence
		return cls.merge_profile(result)


	@classmethod
	def merge_profile(cls, profile, overrides=None):
		import copy

		result = copy.deepcopy(defaults)
		for k in result.keys():
			profile_value = None
			override_value = None

			if k in profile:
				profile_value = profile[k]
			if overrides and k in overrides:
				override_value = overrides[k]

			if profile_value is None and override_value is None:
				# neither override nor profile, no need to handle this key further
				continue

			if k in ("start_gcode", "end_gcode"):
				# the array fields need some special treatment. Basically something like this:
				#
				#    override_value: [None, "b"]
				#    profile_value : ["a" , None, "c"]
				#    default_value : ["d" , "e" , "f", "g"]
				#
				# should merge to something like this:
				#
				#                    ["a" , "b" , "c", "g"]
				#
				# So override > profile > default, if neither override nor profile value are available
				# the default value should just be left as is

				for x in xrange(len(result[k])):
					if override_value is not None and  x < len(override_value) and override_value[x] is not None:
						# we have an override value for this location, so we use it
						result[k][x] = override_value[x]
					elif profile_value is not None and x < len(profile_value) and profile_value[x] is not None:
						# we have a profile value for this location, so we use it
						result[k][x] = profile_value[x]

			else:
				# just change the result value to the override_value if available, otherwise to the profile_value if
				# that is given, else just leave as is
				if override_value is not None:
					result[k] = override_value
				elif profile_value is not None:
					result[k] = profile_value
		return result

	def __init__(self, profile):
		self.profile = profile

	def get(self, key):
		if key in self.profile:
			return self.profile[key]
		elif key in defaults:
			return defaults[key]
		else:
			return None

	def get_int(self, key, default=None):
		value = self.get(key)
		if value is None:
			return default

		try:
			return int(value)
		except ValueError:
			return default

	def get_float(self, key, default=None):
		value = self.get(key)
		if value is None:
			return default

		if isinstance(value, (str, unicode, basestring)):
			value = value.replace(",", ".").strip()

		try:
			return float(value)
		except ValueError:
			return default

	def get_boolean(self, key, default=None):
		value = self.get(key)
		if value is None:
			return default

		if isinstance(value, bool):
			return value
		elif isinstance(value, (str, unicode, basestring)):
			return value.lower() == "true" or value.lower() == "yes" or value.lower() == "on" or value == "1"
		elif isinstance(value, (int, float)):
			return value > 0
		else:
			return value == True

	def get_microns(self, key, default=None):
		value = self.get_float(key, default=None)
		if value is None:
			return default
		return int(value * 1000)

	def get_gcode_template(self, key):
		extruder_count = s.globalGetInt(["printerParameters", "numExtruders"])

		if key in self.profile:
			gcode = self.profile[key]
		else:
			gcode = defaults[key]

		if key in ("start_gcode", "end_gcode"):
			return gcode[extruder_count-1]
		else:
			return gcode

	def get_machine_extruder_offset(self, extruder, axis):
		extruder_offsets = s.globalGet(["printerParameters", "extruderOffsets"])
		if extruder >= len(extruder_offsets):
			return 0.0
		if axis.lower() not in ("x", "y"):
			return 0.0
		return extruder_offsets[extruder][axis.lower()]

	def get_profile_string(self):
		import base64
		import zlib

		import copy
		profile = copy.deepcopy(defaults)
		profile.update(self.profile)
		for key in ("print_temperature", "print_temperature2", "print_temperature3", "print_temperature4",
		            "filament_diameter", "filament_diameter2", "filament_diameter3", "filament_diameter4"):
			profile[key] = self.get(key)

		result = []
		for k, v in profile.items():
			if isinstance(v, (str, unicode)):
				result.append("{k}={v}".format(k=k, v=v.encode("utf-8")))
			else:
				result.append("{k}={v}".format(k=k, v=v))

		return base64.b64encode(zlib.compress("\b".join(result), 9))

	def replaceTagMatch(self, m):
		import time

		pre = m.group(1)
		tag = m.group(2)

		if tag == 'time':
			return pre + time.strftime('%H:%M:%S')
		if tag == 'date':
			return pre + time.strftime('%d-%m-%Y')
		if tag == 'day':
			return pre + ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][int(time.strftime('%w'))]
		if tag == 'profile_string':
			return pre + 'svgtogcode_OCTO_PROFILE_STRING:%s' % (self.get_profile_string())

		if pre == 'F' and tag == 'max_z_speed':
			f = self.get_float("travel_speed") * 60
		elif pre == 'F' and tag in ['print_speed', 'retraction_speed', 'travel_speed', 'bottom_layer_speed', 'cool_min_feedrate']:
			f = self.get_float(tag) * 60
		elif self.get(tag):
			f = self.get(tag)
		else:
			return '%s?%s?' % (pre, tag)

		if (f % 1) == 0:
			return pre + str(int(f))

		return pre + str(f)

	def get_gcode(self, key):
		extruder_count = s.globalGetInt(["printerParameters", "numExtruders"])

		prefix = ""
		postfix = ""

		if self.get("gcode_flavor") == GcodeFlavors.ULTIGCODE:
			if key == "end_gcode":
				return "M25 ;Stop reading from this point on.\n;svgtogcode_PROFILE_STRING:%s\n" % (self.get_profile_string())
			return ""

		if key == "start_gcode":
			contents = self.get_gcode_template("start_gcode")

			e_steps = self.get_float("steps_per_e")
			if e_steps > 0:
				prefix += "M92 E{e_steps}\n" % (e_steps)
			temp = self.get_float("print_temperature")

			bedTemp = 0
			if self.get_boolean("has_heated_bed"):
				bedTemp = self.get_float("print_bed_temperature")
			include_bed_temps = bedTemp > 0 and not "{print_bed_temperature}" in Profile.regex_strip_comments.sub("", contents)

			if include_bed_temps:
				prefix += "M140 S{print_bed_temperature}\n"

			if temp > 0 and not "{print_temperature}" in Profile.regex_strip_comments.sub("", contents):
				if extruder_count > 0:
					def temp_line(temp, extruder, template):
						t = temp
						if extruder > 0:
							print_temp = self.get_float("print_temperature%d" % (extruder + 1))
							if print_temp > 0:
								t = print_temp
						return template.format(extruder=extruder, temp=t)
					for n in xrange(1, extruder_count):
						prefix += temp_line(temp, n, "M104 T{extruder} S{temp}\n")
					for n in xrange(0, extruder_count):
						prefix += temp_line(temp, n, "M109 T{extruder} S{temp}\n")
					prefix += "T0\n"
				else:
					prefix += "M109 S{temp}\n".format(temp=temp)

			if include_bed_temps:
				prefix += "M190 S{print_bed_temperature}\n".format(bedTemp=bedTemp)

		else:
			contents = self.get_gcode_template(key)

		return unicode(prefix + re.sub("(.)\{([^\}]*)\}", self.replaceTagMatch, contents).rstrip() + '\n' + postfix).strip().encode('utf-8') + '\n'

	def calculate_edge_width_and_line_count(self):
		wall_thickness = self.get_float("wall_thickness")
		nozzle_size = self.get_float("nozzle_size")

		if self.get_boolean("spiralize") or self.get_boolean("follow_surface"):
			return wall_thickness, 1
		if wall_thickness < 0.01:
			return nozzle_size, 0
		if wall_thickness < nozzle_size:
			return wall_thickness, 1

		edge_width = None
		line_count = int(wall_thickness / (nozzle_size - 0.0001))
		if line_count < 1:
			edge_width = nozzle_size
			line_count = 1
		line_width = wall_thickness / line_count
		line_width_alt = wall_thickness / (line_count + 1)
		if line_width > nozzle_size * 1.5:
			return line_width_alt, line_count + 1
		if not edge_width:
			edge_width = line_width
		return edge_width, line_count

	def calculate_solid_layer_count(self):
		layer_height = self.get_float("layer_height")
		solid_thickness = self.get_float("solid_layer_thickness")
		if layer_height == 0.0:
			return 1
		import math
		return int(math.ceil(solid_thickness / (layer_height - 0.0001)))

	def calculate_minimal_extruder_count(self):
		extruder_count = s.globalGetInt(["printerParameters", "numExtruders"])
		if extruder_count < 2:
			return 1
		if self.get("support") == SupportLocationTypes.NONE:
			return 1
		if self.get("support_dual_extrusion") == SupportDualTypes.SECOND:
			return 2
		return 1

	def convert_to_engine(self):

		settings = {
			"--engraving-laser-speed": self.get_int("speed"),
			"--laser-intensity": self.get_int("intensity")
		}

		return settings
