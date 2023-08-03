import glob
import random
import os


class Shortcode():
	def __init__(self, Unprompted):
		self.Unprompted = Unprompted
		self.description = "Processes the file content of 'path.'"

	def run_atomic(self, pargs, kwargs, context):
		self.log.warning(f"As of v9.14.0, [file] is a legacy shortcode and will eventually be removed in favor of [call] - the main difference is that [call] also works with functions.")
		if "_bypass_if" in kwargs:
			if self.Unprompted.parse_advanced(kwargs["_bypass_if"], context): return ""

		file_string = self.Unprompted.parse_alt_tags(pargs[0], context)
		this_encoding = self.Unprompted.parse_advanced(kwargs["_encoding"], context) if "_encoding" in kwargs else "utf-8"

		# Relative path
		if (file_string[0] == "."):
			path = os.path.dirname(context) + "/" + file_string + self.Unprompted.Config.txt_format
		# Absolute path
		else:
			path = self.Unprompted.base_dir + "/" + self.Unprompted.Config.template_directory + "/" + file_string + self.Unprompted.Config.txt_format

		files = glob.glob(path)
		if (len(files) == 0):
			self.log.error(f"No files found at this location: {path}")
			return ("")
		file = random.choice(files)

		self.log.debug(f"Loading file: {file}")

		if not os.path.exists(file):
			self.log.error(f"File does not exist: {file}")
			return ("")

		with open(file, "r", encoding=this_encoding) as f:
			file_contents = f.read()
		f.close()

		# Use [set] with keyword arguments
		for key, value in kwargs.items():
			if (key[0] == "_"): continue  # Skips system arguments
			self.Unprompted.shortcode_objects["set"].run_block([key], {}, context, value)

		self.Unprompted.conditional_depth = 0
		return (self.Unprompted.process_string(file_contents, path))

	def ui(self, gr):
		gr.Textbox(label="Function name or filepath 🡢 str", max_lines=1)
		gr.Textbox(label="Expected encoding 🡢 _encoding", max_lines=1, value="utf-8")
		pass