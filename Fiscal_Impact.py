import sys, os, string, math, arcpy, traceback, psutil
arcpy.env.overwriteOutput = True

analysisItem = arcpy.GetParameterAsText(0) #Roads, Sewers, Manholes, etc
censusBlocks = arcpy.GetParameterAsText(1) #Census Blocks to be used for population allotment.
popField = arcpy.GetParameterAsText(2) #Field name with the total population value
boundary = arcpy.GetParameterAsText(3) #Boundary to clip data within.
dissolveFeature = arcpy.GetParameterAsText(4) #Feature to dissolve from census blocks. (ie - River)
outputPath = arcpy.GetParameterAsText(5)     #Output folderlocation.
fishnetSize = arcpy.GetParameterAsText(6)

outputWorkspace = os.path.dirname(outputPath)
arcpy.env.workspace = outputPath
arcpy.env.scratchWorkspace = os.path.dirname(outputPath)
sys.path.append(outputWorkspace)


try:
    arcpy.ClearWorkspaceCache_management()
    arcpy.AddMessage("Hello World!")
    arcpy.AddMessage(analysisItem)
    arcpy.AddMessage(censusBlocks)
    arcpy.AddMessage(popField)
    arcpy.AddMessage(boundary)
    arcpy.AddMessage(dissolveFeature)
    arcpy.AddMessage(outputWorkspace )


    #Step 1: ERASE hydrography and other features from the census blocks.
    if dissolveFeature and dissolveFeature != "#":
        arcpy.AddMessage("dissolving")
        tempCensusDissolve = "tempCensusDissolve"
        arcpy.Erase_analysis(censusBlocks, dissolveFeature, tempCensusDissolve,)
    else:
        arcpy.AddMessage("not dissolving")
        tempCensusDissolve = "tempCensusDissolve"
        arcpy.FeatureClassToFeatureClass_conversion(censusBlocks, outputPath, "tempCensusDissolve","","","")

    #Step 2: Add field and calculate area of census blocks.

    arcpy.AddField_management("tempCensusDissolve.shp", "AcresOrig", "DOUBLE","","","","","","")
    arcpy.CalculateField_management("tempCensusDissolve.shp", "AcresOrig", "!shape.area@acres!",
        "PYTHON_9.3","#")

    #Step 3: Create Fishnet

    desc = arcpy.Describe(boundary)
    arcpy.CreateFishnet_management("tempFishnet",str(desc.extent.lowerLeft),str(desc.extent.XMin) + " " + str(desc.extent.YMax + 10),fishnetSize, fishnetSize,0,0,str(desc.extent.upperRight), "NO_LABELS", boundary, "POLYGON")

    #Step 4: Select just the Grid Cells that touch the boundaries or interior.

    #The layer needs to be added to the dataframe first for the selection tool to work.
    mxd = arcpy.mapping.MapDocument("CURRENT")
    df = arcpy.mapping.ListDataFrames(mxd,"*")[0]
    fishnetLayer = arcpy.mapping.Layer("tempFishnet.shp")
    arcpy.mapping.AddLayer(df, fishnetLayer,"TOP")

    #Select fishnet grids that overlap with boundary and export to new shapefile.
    arcpy.SelectLayerByLocation_management(fishnetLayer, "",boundary,"", "NEW_SELECTION", "")
    arcpy.FeatureClassToFeatureClass_conversion(fishnetLayer, outputPath, "tempFishnetSelected","","","")

    #Remove old fishnet layer and delete the shapefile before adding the new one.
    for lyr in arcpy.mapping.ListLayers(mxd, "", df):
        if lyr.name == "tempFishnet":
            arcpy.mapping.RemoveLayer(df, lyr)
    arcpy.Delete_management("tempFishnet.shp")

    #Redefine and add new fishnet layer.
    fishnetLayer = arcpy.mapping.Layer("tempFishnetSelected.shp")
    arcpy.mapping.AddLayer(df, fishnetLayer,"TOP")

    #Step 6: Cut Census Blocks into Fishtnet. Calculate Cut Blocks in Acres.

    arcpy.Intersect_analysis (["tempCensusDissolve.shp", "tempFishnetSelected.shp"], "censusBlocksCut", "ALL","","")

    #Add cut Census Blocks  (After checking to make sure it already isn't added) to the map.
    for lyr in arcpy.mapping.ListLayers(mxd, "", df):
        if lyr.name == "censusBlocksCut":
            arcpy.mapping.RemoveLayer(df, lyr)
    censusBlocksCut = arcpy.mapping.Layer("censusBlocksCut.shp")
    arcpy.mapping.AddLayer(df,censusBlocksCut,"TOP")

    arcpy.AddField_management(censusBlocksCut, "AcresCut", "DOUBLE","","","","","","")
    arcpy.CalculateField_management("censusBlocksCut.shp", "AcresCut", "!shape.area@acres!",
        "PYTHON_9.3","#")

    #Step 7: Allocate Pop into area of Cut Blocks

    #Need to add the cut census blocks, select the ones with zero pop and export a subset.
    # (Then remove the old cut census block shapefile from the map and delete.)

    arcpy.SelectLayerByAttribute_management(censusBlocksCut, "NEW_SELECTION", str(popField)+"<> 0 ")

    #Export all non-zero pop Census Blocks and remove from dataframe.
    arcpy.FeatureClassToFeatureClass_conversion(censusBlocksCut, outputPath, "censusBlocksCutWpop","","","")

    for lyr in arcpy.mapping.ListLayers(mxd, "", df):
        if lyr.name == "censusBlocksCut":
            arcpy.mapping.RemoveLayer(df, lyr)
    arcpy.Delete_management("censusBlocksCut.shp")

    #Calculate the allocated population for the smaller cut census blocks.
    arcpy.AddField_management("censusBlocksCutWpop.shp", "PopCut", "DOUBLE","","","","","","")
    expression = '!%s!*(!AcresCut! / !AcresOrig!)' % popField
    arcpy.CalculateField_management("censusBlocksCutWpop.shp","PopCut", expression,"PYTHON_9.3","")

    #Step 8: Sum Population into Fishnet Squares w/ Spatial Join.

    #Convert all Census Blocks into Points so that they can be joined and summed into the cells w/o double counting.

    arcpy.FeatureToPoint_management("censusBlocksCutWpop.shp", "tempCensusPopPoints.shp", "INSIDE")

################################################################################################################

#In here i need to add a section to calculate the area of the cut census block, and then
#Add area to field map so that I can sum the census block area into the final grid.
#      (this will give a better area for calculating pop density)

################################################################################################################

    # In order to merge and sum the population, you have to go through all of this field mapping first.
    in_file = "tempCensusPopPoints.shp"
    out_file = 'fishnetWithPopulationJoin'
    #Field mapping.
    fm = arcpy.FieldMap()
    fms = arcpy.FieldMappings()
    for field in arcpy.ListFields(in_file, "PopCut"):
        fm.addInputField(in_file, field.name)
    fm.mergeRule = "Sum"
    f_name = fm.outputField
    f_name.name = "Sum_Pop"
    fm.outputField = f_name
    fms.addFieldMap(fm)

    #Now that the field mapping and merge rule is set, you can perform the spatial join.

    arcpy.SpatialJoin_analysis("tempFishnetSelected.shp", in_file, out_file,"JOIN_ONE_TO_ONE","KEEP_ALL",fms)


    #Clean up and remove all of the temporary files.
    arcpy.Delete_management("censusBlocksCut.shp")
    arcpy.Delete_management("censusBlocksCutWpop.shp")
    arcpy.Delete_management("tempCensusPopPoints.shp")
    arcpy.Delete_management("tempCensusDissolve.shp")
    for lyr in arcpy.mapping.ListLayers(mxd, "", df):
        if lyr.name == "tempFishnetSelected":
            arcpy.mapping.RemoveLayer(df, lyr)
    arcpy.Delete_management("tempFishnetSelected.shp")

    #Add final product from this analysis: A fishnet with population allocated from Census Blocks
    fishnetPopLayer = arcpy.mapping.Layer("fishnetWithPopulationJoin.shp")
    arcpy.mapping.AddLayer(df, fishnetPopLayer,"TOP")


except Exception as e:
    arcpy.AddError('\n' + "Script failed because: \t\t" + e.message )
    exceptionreport = sys.exc_info()[2]
    fullermessage   = traceback.format_tb(exceptionreport)[0]
    arcpy.AddError("at this location: \n\n" + fullermessage + "\n")
