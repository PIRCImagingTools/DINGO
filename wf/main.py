import nipype.pipeline.engine as pe
from nipype.interfaces import fsl
from DSI_Studio import *

#Create EddyCorrect node
eddyc = pe.Node(interface=fsl.EddyCorrect(),name="eddyc")
eddyc.inputs.in_file = dti_file
eddyc.inputs.out_file = ec_file
eddyc.inputs.ref_num = 0

#Create Robust BET node
rbet = pe.Node(interface=fsl.BET(),name="rbet")
rbet.inputs.in_file = ec_file
rbet.inputs.out_file = be_file
rbet.inputs.robust = True
rbet.inputs.mask = True
