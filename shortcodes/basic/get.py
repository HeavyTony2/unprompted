class Shortcode():
	def __init__(self, Unprompted):
		self.Unprompted = Unprompted
		self.description = "Returns the value of a variable."

	def run_atomic(self, pargs, kwargs, context):
		_default = str(self.Unprompted.parse_advanced(kwargs["_default"], context)) if "_default" in kwargs else ""
		_sep = str(self.Unprompted.parse_advanced(kwargs["_sep"], context)) if "_sep" in kwargs else " "

		return_string = ""

		if "_all_external" in kwargs:
			filepath = self.Unprompted.parse_filepath(self.Unprompted.str_with_ext(kwargs["_all_external"]),root=self.Unprompted.base_dir,must_exist=False)

			json_obj = self.Unprompted.create_load_json(filepath)

			for key, value in json_obj.items():
				self.Unprompted.shortcode_user_vars[key] = value

		for idx, parg in enumerate(pargs):
			self.Unprompted.is_var_deprecated(parg)

			if idx == 0:
				if "_var" in kwargs: parg = self.Unprompted.parse_alt_tags(kwargs["_var"], context)
			else: return_string += _sep

			if ("_before" in kwargs):
				return_string = f"{kwargs['_before']}{return_string}"
			if ("_after" in kwargs):
				return_string = f"{return_string}{kwargs['_after']}"

			if "_external" in kwargs:
				filepath = self.Unprompted.parse_filepath(self.Unprompted.str_with_ext(kwargs["_external"]),root=self.Unprompted.base_dir,must_exist=False)
				json_obj = self.Unprompted.create_load_json(filepath)
				if parg in json_obj:
					self.Unprompted.shortcode_user_vars[parg] = json_obj[parg]
					return_string += str(json_obj[parg])
				else:
					return_string += _default
			elif (parg in self.Unprompted.shortcode_user_vars):
				this_var = self.Unprompted.shortcode_user_vars[parg]
				if (isinstance(this_var, list)): return_string += _sep.join(str(x) for x in this_var)
				else: return_string += str(this_var)
			else:
				return_string += _default

		return (return_string)

	def ui(self, gr):
		gr.Textbox(label="Variable to get 🡢 str", max_lines=1, placeholder="my_var")
		gr.Textbox(label="Default value if the variable doesn't exist 🡢 _default", max_lines=1)
		gr.Textbox(label="Separator string when returning multiple variables 🡢 _sep", max_lines=1)
		gr.Textbox(label="String to prepend to the variable 🡢 _before", max_lines=1)
		gr.Textbox(label="String to append to the variable 🡢 _after", max_lines=1)
