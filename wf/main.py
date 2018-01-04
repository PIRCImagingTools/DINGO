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

for root,dirs,files in os.walk(anacfg["data_dir"]):#parent to subject files
	for f in files:
		if re.search('config\.json(?!~)',f): #ignore old versions
			potential = read_config(os.path.abspath(os.path.join(root,f)))
			try:
				pot_id = patient_scan(potential,addSequence=True)
				t_pot_id = frozenset([pot_id])
				if bool(t_scanlist.intersection(t_pot_id)):
					print("%s: INCLUDED" % (pot_id))
					subcfg = potential
				else:
					print("%s: SKIPPED - does not match inclusion list" % 
						 (pot_id))
			except KeyError:#not a subject config file
				pass



###Pre-Processing###
prepin = pe.Node(IdentityInterface(fields["subscan_list"]),
				 name="prepin")

#Get Data node
templates = {"dwi": "/{sub_id}/{scan_id}/{sub_id}_{scan_id}_{uid}.nii.gz",
			 "bvals":"/{sub_id}/{scan_id}/{sub_id}_{scan_id}_{uid}.bval",
			 "bvecs":"/{sub_id}/{scan_id}/{sub_id}_{scan_id}_{uid}.bvec"}
sf = pe.MapNode(SelectFiles(templates),
				name="selectfiles")

sf.inputs.base_directory = anc["data_dir"]
sf.inputs.sub_id = sbc["pid"]
sf.inputs.scan_id = sbc["scanid"]
sf.inputs.uid = sbc["sequenceid"]

#Create ReOrient2Std node
reorient = pe.MapNode(interface=fsl.Reorient2Std(), 
						name="reorient")

#Create EddyCorrect node
eddyc = pe.MapNode(interface=fsl.EddyCorrect(),
					name="eddyc")
eddyc.inputs.ref_num = 0

#Create Robust BET node
rbet = pe.MapNode(interface=fsl.BET(),
					name="rbet")
rbet.inputs.robust = True
rbet.inputs.mask = True

#Create DTIFit node
dti = pe.MapNode(interface=fsl.DTIFit(),
					name="dti")
dti.inputs.base_name = patient_scan(sbc, addSequence=True)

prepout = pe.Node(interface=IdentityInterface(fields=["fa_list"]),
					name="prepout")


#Preprocess workflow
prep = pe.Workflow(name="prep")
prep.base_dir = sbc["paths"]["base_dir"]
prep.connect([
			(sf, reorient, [("dwi","in_file")]),
			(sf, dti, [("bvals", "bvals")]),
			(sf, dti, [("bvecs", "bvecs")]),
			(reorient, eddyc, [("out_file","in_file")]),
			(eddyc, rbet, [("out_file","in_file")]),
			(eddyc, dti, [("out_file","dwi")]),
			(rbet, dti, [("mask_file","mask")]),
			(dti, outputnode, [("FA", "fa_list")])
			 ])



def create_tbss_2_reg_n(name="tbss_2_reg_n")
	"""TBSS nonlinear registration:
	Performs tbss_2_reg -n
	"""
	from nipype import IdentityInterface

	inputnode = pe.Node(interface=IdentityInterface(fields=["fa_list",
															"mask_list",
															"target"]),
						name="inputnode")




tbssin = pe.Node(IdentityInterface(fields=["fa_list"]),
				 name="tbssin")

#Copy FA files to new directory

#TBSS1
tbss1 = create_tbss_1_preproc("tbss1")

#TBSS2
tbss2 = create_tbss_2_reg_n("tbss2")

#TBSS3
tbss3 = create_tbss_3_postreg("tbss3")

tbss = pe.Workflow(name="tbss")
tbss.connect([
			(tbssin, tbss1, [("","")],
			(tbss1, tbss2, [("","")],
			(tbss2, tbss3, [("","")]
			])



wf = pe.Workflow(name="tbss_reg")
wf.connect([
			(prepflow, tbssflow, (["outputnode.FA","inputnode.fa_list"])
			])
