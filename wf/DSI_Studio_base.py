from nipype.interfaces.base import traits, CommandLine, CommandLineInputSpec, PackageInfo
import os
from nipype.utils.filemanip import fname_presuffix

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
			self._output_type = Info.action_to_output_type(self.inputs.action)

		if not isdefined(self.inputs.output_type):
			self.inputs.output_type = self._output_type
		else:
			self._output_update()

	def _output_update(self):
		self._output_type = self.inputs.output_type

	def _gen_fname(self, basename, cwd=None, suffix=None, change_ext=True, ext=None):
		"""Generate a filename based on input.
		
		Parameters
		----------
		basename : str (filename to base the new filename)
		cwd : str (path to prefix the new filename)
		suffix : str (suffix to add to the basename)
		change_ext : bool (flag to change the filename extension to
			corresponding output type for action)

		Returns
		-------
		fname : str (new filename based on input)
		"""

		if basename == "":
			raise ValueError("Unable to generate filename for command %s." % (self.cmd))
		if cwd is None:
			cwd = os.getcwd()
		if ext is None:
			ext = Info.output_type_to_ext(self.inputs.output_type)
		if change_ext:
			if suffix:
				suffix = "".join((suffix, ext))
			else:
				suffix = ext
		if suffix is None:
			suffix = ""
		fname = fname_presuffix(basename, suffix=suffix, use_ext=False,
								newpath=cwd)
		return fname


class DSIStudioTrack(DSIStudioCommand):
	"""DSI Studio tracking action support
	"""
	

class DSIStudioAnalysis(DSIStudioCommand):
	"""DSI Studio analysis action support
	"""

class DSIStudioInputSpec(CommandLineInputSpec):
	"""Base input specification for DSI Studio commands.
	"""
