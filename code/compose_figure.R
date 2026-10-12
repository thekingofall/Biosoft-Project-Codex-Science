suppressPackageStartupMessages(library(jsonlite))
suppressPackageStartupMessages(library(grid))
if (!requireNamespace("png", quietly=TRUE)) stop("Install the R png package")
p <- fromJSON(commandArgs(trailingOnly=TRUE)[[1]], simplifyVector=FALSE)
if (p$font != "Arial") stop("Figure labels require Arial")
if (.Platform$OS.type == "windows") windowsFonts(Arial=windowsFont("Arial"))
images <- lapply(p$panels, function(panel) png::readPNG(panel$path, native=TRUE))

draw <- function() {
  grid.newpage()
  for (i in seq_along(p$panels)) {
    panel <- p$panels[[i]]
    cell_w <- p$width_mm * panel$column_span / p$columns
    cell_h <- p$height_mm * panel$row_span / p$rows
    left <- p$width_mm * panel$column / p$columns + p$gap_mm / 2
    top <- p$height_mm * (1 - panel$row / p$rows) - p$gap_mm / 2
    available_w <- cell_w - p$gap_mm
    available_h <- cell_h - p$gap_mm - p$label_height_mm
    if (available_w <= 0 || available_h <= 0) stop("Panel has no drawing area")
    img <- images[[i]]
    ratio <- ncol(img) / nrow(img)
    image_w <- min(available_w, available_h * ratio)
    image_h <- image_w / ratio
    if (isTRUE(p$panel_letters)) {
      grid.text(LETTERS[[i]], x=unit(left,"mm"), y=unit(top,"mm"),
                just=c("left","top"),
                gp=gpar(fontfamily="Arial",fontface="bold",fontsize=p$letter_size_pt,col="black"))
    }
    x <- left + available_w / 2
    y <- top - p$label_height_mm - available_h / 2
    grid.raster(img, x=unit(x,"mm"), y=unit(y,"mm"),
                width=unit(image_w,"mm"),height=unit(image_h,"mm"),interpolate=FALSE)
  }
}

cairo_pdf(paste0(p$output_prefix,".pdf"),width=p$width_mm/25.4,
          height=p$height_mm/25.4,family="Arial",pointsize=12,bg="white")
draw()
invisible(dev.off())
png(paste0(p$output_prefix,".png"),width=p$width_mm,height=p$height_mm,
    units="mm",res=300,bg="white",type=if(.Platform$OS.type=="windows") "windows" else "cairo")
draw()
invisible(dev.off())
