class Shortcode():
	"""Use in conjunction with [case] to run different logic blocks depending on the value of a var."""
	def __init__(self,Unprompted):
		self.Unprompted = Unprompted
		self.switch_var = ""

	def run_block(self, pargs, kwargs, context,content):
		self.switch_var = self.Unprompted.parse_alt_tags(pargs[0],context)
		return(self.Unprompted.parse_alt_tags(content,context))

	def cleanup(self):
		self.switch_var = ""