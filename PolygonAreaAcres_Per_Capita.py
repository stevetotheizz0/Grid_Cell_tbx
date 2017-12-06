import sys, os, string, math, arcpy, traceback
arcpy.env.overwriteOutput = True

analysisItem = arcpy.GetParameterAsText(0) #Roads, Sewers, Manholes, etc
outputPath = arcpy.GetParameterAsText(1)
censusBlocks = "fishnetWithPopulationJoin.shp" #Census Blocks to be used for population allotment.
popField = "Sum_Pop"

outputWorkspace = outputPath
arcpy.env.workspace = outputPath
arcpy.env.scratchWorkspace = outputPath
sys.path.append(outputPath)


try:

    arcpy.AddMessage("Hello World!")
    arcpy.AddMessage(analysisItem)
    arcpy.AddMessage(censusBlocks)
    arcpy.AddMessage(outputWorkspace )

    #Step 1: Calculate Full Area (Save for QA at End)

    arcpy.AddField_management(analysisItem, "SqFtOrig", "DOUBLE","","","","","","")
    arcpy.CalculateField_management(analysisItem, "SqFtOrig", "!shape.area@acres!",
        "PYTHON_9.3","#")


    def checkArea(fc, field):
            list = []

            rows = arcpy.SearchCursor(fc)
            for row in rows:
                subArea = row.getValue(field)
                list.append(subArea)

            arcpy.AddMessage( sum(list) )

    checkArea(analysisItem,"SqFtOrig")
    #Step 2: Cut to Fishnet and Recalculate Area

    arcpy.Intersect_analysis ([analysisItem, "fishnetWithPopulationJoin.shp"], "analysisItemCut", "ALL","","")
    arcpy.AddField_management("analysisItemCut.shp", "AreaCut", "DOUBLE","","","","","","")
    arcpy.CalculateField_management("analysisItemCut.shp", "AreaCut", "!shape.area@acres!",
        "PYTHON_9.3","#")


    checkArea("analysisItemCut.shp", "AreaCut")

    #Step 3: Convert to Point within Poly for Spatial Join
    #        Remove Area = 0 polygons first.

    arcpy.FeatureToPoint_management("analysisItemCut.shp", "analysisItemCutPoints.shp", "INSIDE")

    # In order to merge and sum the population, you have to go through all of this field mapping first.
    in_file = "analysisItemCutPoints.shp"
    out_file = 'fishnetWithAnalysisTotalJoin'
    fm = arcpy.FieldMap()
    fms = arcpy.FieldMappings()
    for field in arcpy.ListFields(in_file, "AreaCut"):
        fm.addInputField(in_file, field.name)
    fm.mergeRule = "Sum"
    f_name = fm.outputField
    f_name.name = "Sum_Area"
    fm.outputField = f_name
    fms.addTable(censusBlocks)
    fms.addFieldMap(fm)
    #Now that the field mapping and merge rule is set, you can perform the spacial join.

    #Step 4: Spatial Join with Fishnet and Sum Area

    arcpy.SpatialJoin_analysis(censusBlocks, in_file, "%s.shp" % out_file,"JOIN_ONE_TO_ONE","KEEP_ALL",fms)
    checkArea("%s.shp" % out_file, "Sum_Area")

    arcpy.AddField_management("%s.shp" % out_file, "CellAcres", "DOUBLE","","","","","","")
    arcpy.CalculateField_management("%s.shp" % out_file, "CellAcres", "!shape.area@acres!",
        "PYTHON_9.3","#")

    mxd = arcpy.mapping.MapDocument("CURRENT")
    df = arcpy.mapping.ListDataFrames(mxd,"*")[0]
    out_fileLayer = arcpy.mapping.Layer("%s.shp" % out_file)
    arcpy.mapping.AddLayer(df, out_fileLayer,"TOP")


except Exception as e:
    arcpy.AddError('\n' + "Script failed because: \t\t" + e.message )
    exceptionreport = sys.exc_info()[2]
    fullermessage   = traceback.format_tb(exceptionreport)[0]
    arcpy.AddError("at this location: \n\n" + fullermessage + "\n")
