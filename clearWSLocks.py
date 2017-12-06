import os, arcpy, psutil

def clear(inputWS):
	'''Attempts to clear ArcGIS/Arcpy locks on a workspace.

	Two methods:
	 1: if ANOTHER process (i.e. ArcCatalog) has the workspace open, that process is terminated
	 2: if THIS process has the workspace open, it attempts to clear locks using arcpy.Exists, arcpy.Compact and arcpy.Exists in sequence

	Notes:
	 1: does not work well with Python Multiprocessing
	 2: this will kill ArcMap or ArcCatalog if they are accessing the worspace, so SAVE YOUR WORK

	Required imports: os, psutil
	'''

	# get process ID for this process (treated differently)
	thisPID = os.getpid()

	# normalise path
	_inputWS = os.path.normpath(inputWS)

	# get list of currently running Arc/Python processes
	p_List = []
	ps = psutil.process_iter()
	for p in ps:
		if ('Arc' in p.name()) or ('python' in p.name()):
			p_List.append(p.pid)

	# iterate through processes
	for pid in p_List:
		p = psutil.Process(pid)

		# if any have the workspace open
		if any(_inputWS in pth for pth in [fl.path for fl in p.open_files()]):
			print '      !!! Workspace open: %s' % _inputWS

			# terminate if it is another process
			if pid != thisPID:
				print '      !!! Terminating process: %s' % p.name
				p.terminate()
			else:
				print '      !!! This process has workspace open...'

	# if this process has workspace open, keep trying while it is open...
	while any(_inputWS in pth for pth in [fl.path for fl in psutil.Process(thisPID).open_files()]):
		print '    !!! Trying Exists, Compact, Exists to clear locks: %s' % all([arcpy.Exists(_inputWS), arcpy.Compact_management(_inputWS), arcpy.Exists(_inputWS)])

	return True
