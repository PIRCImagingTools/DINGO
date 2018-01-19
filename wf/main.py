from wf.DSI_Studio_base import *
from wf.utils import patient_scan, read_config
from nipype import IdentityInterface, SelectFiles
import nipype.pipeline.engine as pe
from nipype.interfaces import fsl
from nipype.workflows.dmri.fsl import tbss


anacfgpath = os.environ["ana_config"]
anacfg = read_config(anacfgpath)


#Check for included sub/scan list
if "included_psids" in anacfg:
	scanlist = anacfg["included_psids"]
	t_scanlist = frozenset(scanlist)
else:
	raise KeyError("included_psids not identified in analysis config")

#for root,dirs,files in os.walk(anacfg["data_dir"]):#parent to subject files
#	for f in files:
#		if re.search('config\.json(?!~)',f): #ignore old versions
#			potential = read_config(os.path.abspath(os.path.join(root,f)))
#			try:
#				pot_id = patient_scan(potential,addSequence=True)
#				t_pot_id = frozenset([pot_id])
#				if bool(t_scanlist.intersection(t_pot_id)):
#					print("%s: INCLUDED" % (pot_id))
#					subcfg = potential
#				else:
#					print("%s: SKIPPED - does not match inclusion list" % 
#						 (pot_id))
#			except KeyError:#not a subject config file
#				pass



###Pre-Processing###
prepin = pe.Node(interface=IdentityInterface(fields["subscanuid"]),
				 name="prepin")
prepin.iterables = ("subscanuid",scanlist)

splitids = pe.Node(name="splitids",
			interface=Function(input_names=["psid","sep"],
							   output_names=["subid","scanid","uid"],
							   function=split_chpid))
splitids.inputs.sep = "_"
#splitids.inputs.psid=prepin.outputs.subscanuid

#Get Data node
templates = {"dwi": "/{sub_id}/{scan_id}/{sub_id}_{scan_id}_{uid}.nii.gz",
			 "bvals":"/{sub_id}/{scan_id}/{sub_id}_{scan_id}_{uid}.bval",
			 "bvecs":"/{sub_id}/{scan_id}/{sub_id}_{scan_id}_{uid}.bvec"}
sf = pe.Node(name="selectfiles",
			 interface=SelectFiles(templates))
sf.inputs.base_directory = anacfg["data_dir"]
#sf.inputs.sub_id = splitids.outputs.subid
#sf.inputs.scan_id = splitids.outputs.scanid
#sf.inputs.uid = splitids.outputs.uid

#Create ReOrient2Std node
reorient = pe.Node(name="reorient",
				   interface=fsl.Reorient2Std())
#reorient.inputs.in_file = sf.outputs.dwi

#Create EddyCorrect node
eddyc = pe.Node(name="eddyc",
				interface=fsl.EddyCorrect())
eddyc.inputs.ref_num = 0
#eddyc.inputs.in_file = reorient.outputs.out_file

#Create Robust BET node
rbet = pe.Node(name="rbet",
			   interface=fsl.BET())
rbet.inputs.robust = True
rbet.inputs.mask = True
#rbet.inputs.in_file = eddyc.outputs.out_file

#Create DTIFit node
dti = pe.Node(name="dti",
			  interface=fsl.DTIFit())
dti.inputs.base_name = patient_scan(sbc, addSequence=True)
#dti.inputs.bvals = sf.outputs.bvals
#dti.inputs.bvecs = sf.outputs.bvecs
#dti.inputs.dwi = eddyc.outputs.out_file
#dti.inputs.mask = rbet.outputs.mask_file

prepout = pe.JoinNode(name="prepout",
					  interface=IdentityInterface(fields=["fa_list",
														  "mask_list"]))
#prepout.inputs.fa_list = reduce(dti.inputs.FA)
#prepout.inputs.mask_list = reduce(rbet.outputs.mask_file)



#Preprocess workflow
gen_fa = pe.Workflow(name="gen_fa")
gen_fa.base_dir = sbc["paths"]["base_dir"]
gen_fa.connect([
			(prepin, splitids, [("subscanuid","psid")]),
			(sf, reorient, [("dwi","in_file")]),
			(sf, dti, [("bvals", "bvals")]),
			(sf, dti, [("bvecs", "bvecs")]),
			(reorient, eddyc, [("out_file","in_file")]),
			(eddyc, rbet, [("out_file","in_file")]),
			(eddyc, dti, [("out_file","dwi")]),
			(rbet, dti, [("mask_file","mask")]),
			(dti, prepout, [("FA", "fa_list")]),
			(rbet, prepout, [("mask_file","mask_list")])
			 ])



def create_tbss_reg_n(name="tbss_reg_n"):
	"""TBSS nonlinear registration:
	Performs tbss_2_reg -n, in_file, reference are each every fa file
	"""
	from nipype import IdentityInterface

	inputnode = pe.Node(name="inputnode",
						interface=IdentityInterface(fields=["fa_list",
															"mask_list",
															"reference"]))
	inputnode.iterables=("reference",inputnode.inputs.fa_list)
	#inputnode.inputs.fa_list=prepout.outputs.fa_list

	#Registration
	flirt = pe.MapNode(name="flirt",
					   interface=fsl.FLIRT(dof=12),
					   iterfield=["in_file","in_weight","reference"])

	fnirt = pe.MapNode(name="fnirt",
					   interface=fsl.FNIRT(#config_file="FA_2_FMRIB58_1mm"),
	#config in nipype seems to only be output, whereas it's input in fsl, 
	#values from FA_2_FMRIB58_1mm copied below, skips flipped
							#ref_file="FMRIB58_FA_1mm"
							skip_implicit_ref_masking=False,
							skip_implicit_in_masking=False,
							refmask_val=0,
							inmask_val=0,
							subsampling_scheme=[8,4,2,2],
							max_nonlin_iter=[5,5,5,5],
							in_fwhm=[12,6,2,2],
							ref_fwhm=[12,6,2,2],
							regularization_lambda=[300,75,30,30],
							apply_intensity_mapping=[1,1,1,0],
							warp_resolution=(10,10,10),
							skip_lambda_ssq=False,
							regularization_model="bending_energy",
							intensity_mapping_model="global_linear",
							derive_from_ref=False),
					   iterfield=["in_file",
								  "ref_file",
								  "affine_file",
								  "fieldcoeff_file"])

	#Apply xfm
#	appwarp = pe.MapNode(name="appwarp",
#						 interface=fsl.ApplyWarp(relwarp=True),
#						 iterfield=["in_file",
#									"out_file",
#									"ref_file",
#									"field_file"])

	#Estimate mean deformation
	sqrTmean = pe.MapNode(name="sqrTmean",
						 interface=fsl.ImageMaths(op_string="-sqr -Tmean"),
						 iterfield=["in_file",
									"out_file"])
	
	meanmedian = pe.MapNode(name="meanmedian",
							interface=fsl.ImageStats(op_string="-M -P 50"),
							iterfield=["in_files",
									   "output_root"])

	outputnode = pe.Node(interface=IdentityInterface(
							fields=["mat_list",
									"fieldcof_list",
									"mean_median_list"]),
						 name="outputnode")

	#Define workflow
	tbssn = pe.Workflow(name=name)
	tbssn.connect([
				(inputnode, flirt, [("fa_list","in_file")]),
				(inputnode, flirt, [("fa_list","reference")]),
				(inputnode, flirt, [("mask_list","in_weight")]),
				(inputnode, fnirt, [("fa_list","in_file")]),
				(inputnode, fnirt, [("fa_list","reference")]),
				(flirt, fnirt, [("out_matrix_file", "affine_file")]),
				(flirt, outputnode, [("out_matrix_file", "mat_list")]),
				(fnirt, outputnode, [("fieldcoeff_file", "fieldcof_list")]),
				(meanmedian, outputnode, [("out_file", "mean_median_list")])
	])


tbssin = pe.Node(IdentityInterface(fields=["fa_list"]),
				 name="tbssin")

#Copy FA files to new directory

#TBSS1
tbss1 = create_tbss_1_preproc("tbss1")

#TBSS2
tbss2 = create_tbss_2_reg_n("tbss2")

#TBSS3
tbss3 = create_tbss_3_postreg("tbss3")

tbssout = pe.Node(IdentityInterface(fields=["best_target",
											"best_to_mni",
											"to_best_warp_list",
											"mni_fa_list"]),
				  name="tbssout")

tbss = pe.Workflow(name="tbss")
tbss.connect([
			(tbssin, tbss1, [("","")]),
			(tbss1, tbss2, [("","")]),
			(tbss2, tbss3, [("","")]),
			(tbss2, tbssout [("","to_best_warp_list")]),
			(tbss3, tbssout [("","best_target")]),
			(tbss3, tbssout [("","best_to_mni")]),
			(tbss3, tbssout [("","mni_fa_list")])
])



wf = pe.Workflow(name="tbss_reg")
wf.connect([
			(prepflow, tbssflow, (["outputnode.FA","inputnode.fa_list"]))
			])
