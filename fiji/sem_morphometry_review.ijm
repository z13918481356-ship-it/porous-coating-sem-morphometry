// Fiji/ImageJ cross-check for the frozen 12-image SEM subset.
// Run with: Fiji --headless -macro sem_morphometry_review.ijm <review-directory>
// The review directory must contain fiji_review_manifest.csv and inputs/*.tif,
// as created by scripts/build_fiji_review_package.py.
//
// Workflow: calibrated ROI -> Gaussian (sigma 1 px) -> Otsu bright-object mask
// -> binary opening -> Watershed -> Analyze Particles.  Pore fraction is measured
// before watershed; particle metrics are measured after watershed.

macro "SEM morphometry Fiji review" {
    root = getArgument();
    if (root=="") exit("Pass the fiji_review directory as the macro argument.");
    sep = File.separator;
    if (!endsWith(root, sep)) root = root + sep;
    manifestPath = root + "fiji_review_manifest.csv";
    if (!File.exists(manifestPath)) exit("Missing " + manifestPath);
    outputPath = root + "fiji_results.csv";
    masksDir = root + "fiji_masks" + sep;
    File.makeDirectory(masksDir);

    contents = replace(File.openAsString(manifestPath), "\r", "");
    lines = split(contents, "\n");
    File.delete(outputPath);
    File.append("image_id,input_filename,pore_area_fraction,eq_diameter_median_um,circularity_median,object_count\n", outputPath);
    setBatchMode(true);
    run("Set Measurements...", "area perimeter shape decimal=6");

    for (r = 1; r < lengthOf(lines); r++) {
        line = lines[r];
        if (line=="") continue;
        fields = split(line, ",");
        imageID = fields[0];
        filename = fields[1];
        pixelSizeUm = parseFloat(fields[9]);
        minAreaUm2 = parseFloat(fields[12]);
        open(root + "inputs" + sep + filename);
        run("Set Scale...", "distance=1 known=" + d2s(pixelSizeUm, 12) + " unit=um");
        run("8-bit");
        run("Gaussian Blur...", "sigma=1");
        setAutoThreshold("Otsu dark");
        setOption("BlackBackground", true);
        run("Convert to Mask");

        // Count bright foreground pixels before watershed, matching Python's area metric.
        getHistogram(values, counts, 256);
        foregroundPixels = counts[255];
        poreFraction = 1 - foregroundPixels / (getWidth() * getHeight());
        run("Open");
        run("Watershed");
        saveAs("Tiff", masksDir + imageID + "_mask.tif");
        run("Clear Results");
        run("Analyze Particles...", "size=" + d2s(minAreaUm2, 12) + "-Infinity circularity=0.00-1.00 show=Nothing display clear");
        n = nResults;
        if (n == 0) {
            File.append(imageID + "," + filename + "," + d2s(poreFraction, 8) + ",NaN,NaN,0\n", outputPath);
        } else {
            diameters = newArray(n);
            circularities = newArray(n);
            for (i = 0; i < n; i++) {
                area = getResult("Area", i);
                diameters[i] = 2 * sqrt(area / PI);
                circularities[i] = getResult("Circ.", i);
            }
            Array.sort(diameters);
            Array.sort(circularities);
            if (n % 2 == 1) {
                medianDiameter = diameters[floor(n / 2)];
                medianCircularity = circularities[floor(n / 2)];
            } else {
                medianDiameter = (diameters[n / 2 - 1] + diameters[n / 2]) / 2;
                medianCircularity = (circularities[n / 2 - 1] + circularities[n / 2]) / 2;
            }
            File.append(imageID + "," + filename + "," + d2s(poreFraction, 8) + "," + d2s(medianDiameter, 8) + "," + d2s(medianCircularity, 8) + "," + n + "\n", outputPath);
        }
        close("*");
    }
    setBatchMode(false);
    print("Wrote " + outputPath);
}
