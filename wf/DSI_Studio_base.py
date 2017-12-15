from nipype.interfaces.base import traits, CommandLine, CommandLineInputSpec, PackageInfo

class Info(PackageInfo):
	ftypes = {'SRC': '.src.gz',
		  'FIB': '.fib.gz',
		  'NIFTI': '.nii.gz',
		  'TRK': '.trk.gz',
		  'TXT': '.txt'}

	act_out = {'trk': 'TRK',
		   'rec': 'FIB',
		   'src': 'SRC',
		   'ana': 'TXT'}

	@classmethod
	def output_type_to_ext(cls, output_type):
		"""Get file extension for given output type

		Parameters
		----------
		output_type : {'SRC', 'FIB', 'NIFTI', 'TRK', 'TXT'}
			String specifying the output type

		Returns
		-------
		extension : str
			The file extension for the output type
		"""

		try:
			return cls.ftypes[output_type]
		except KeyError:
			msg = 'Invalid DSIStudioOUTPUTTYPE: ', output_type
			raise KeyError(msg)

	@classmethod
	def action_to_output_type(cls, action_type):
		"""Get DSI studio output extension per action type

		Returns
		-------
		extension : str
			The file extension for the action type
		"""

		try:
			return cls.act_out[action_type]
		except KeyError:
			msg = 'Invalid DSIStudioACTIONTYPE: ', action_type
			raise KeyError(msg)
	
class DSIStudioCommand(CommandLine):
	"""Base support for DSI Studio commands.
	"""

	_output_type = None

	def __init__(self, **inputs):
		super(DSIStudioCommand, self).__init__(**inputs)
		self.inputs.on_trait_change(self._output_update, 'output_type')

		if self._output_type is None:
			self._output_type = Info.output_type()

		if not isdefined(self.inputs.output_type):
			self.inputs.output_type = self._output_type
		else:
			self._output_update()

	def _output_update(self):
		self._output_type = self.inputs.output_type

		
