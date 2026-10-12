suppressPackageStartupMessages(library(jsonlite))
p <- fromJSON(commandArgs(trailingOnly=TRUE)[[1]])
d <- read.csv(p$csv,check.names=FALSE,stringsAsFactors=FALSE,colClasses="character",na.strings=NULL)
d[[p$y]] <- suppressWarnings(as.numeric(d[[p$y]]))
if(p$kind %in% c("scatter","line")) d[[p$x]] <- suppressWarnings(as.numeric(d[[p$x]]))
if (!is.numeric(d[[p$y]]) || any(!is.finite(d[[p$y]]))) stop("Y must contain finite numeric values")
if (p$kind %in% c("scatter","line") && (!is.numeric(d[[p$x]]) || any(!is.finite(d[[p$x]])))) stop("X must contain finite numeric values")
groups <- if(nzchar(p$group)) unique(as.character(d[[p$group]])) else "All"
if(length(groups)>length(p$palette)) stop("Use at most six groups for this palette")
gid <- if(nzchar(p$group)) match(d[[p$group]],groups) else rep(1,nrow(d))
cols <- p$palette[seq_along(groups)]
if(.Platform$OS.type=="windows") windowsFonts(Arial=windowsFont("Arial"))
draw <- function() {
  par(family="Arial",mar=c(4.2,4.3,.8,if(length(groups)>1) 6 else 1),mgp=c(2.5,.7,0),
      lwd=1.7,las=1,tcl=-.25,cex.axis=1,cex.lab=1.1,xpd=FALSE,bty="l")
  if(p$kind %in% c("scatter","line")) {
    plot(d[[p$x]],d[[p$y]],type="n",xlab=p$x_label,ylab=p$y_label)
    for(i in seq_along(groups)) {
      rows <- which(gid==i); rows <- rows[order(d[[p$x]][rows])]
      if(p$kind=="line") lines(d[[p$x]][rows],d[[p$y]][rows],col=cols[[i]],lwd=2)
      points(d[[p$x]][rows],d[[p$y]][rows],pch=16,col=adjustcolor(cols[[i]],alpha.f=.85),cex=1.1)
    }
  } else {
    levels_x <- unique(as.character(d[[p$x]]))
    if(p$kind=="bar") {
      values <- matrix(NA_real_,nrow=length(groups),ncol=length(levels_x),dimnames=list(groups,levels_x))
      for(i in seq_len(nrow(d))) values[gid[[i]],match(d[[p$x]][[i]],levels_x)] <- d[[p$y]][[i]]
      barplot(values,beside=TRUE,col=cols,border="black",xlab=p$x_label,ylab=p$y_label,ylim=range(c(0,values),na.rm=TRUE))
    } else {
      factor_x <- factor(d[[p$x]],levels=levels_x)
      factor_g <- factor(gid,levels=seq_along(groups))
      split_values <- split(d[[p$y]],interaction(factor_g,factor_x,drop=TRUE))
      names(split_values) <- sub("^[0-9]+\\.","",names(split_values))
      colours <- cols[as.integer(sub("\\..*$","",levels(interaction(factor_g,factor_x,drop=TRUE))))]
      boxplot(split_values,col=colours,border="black",xlab=p$x_label,ylab=p$y_label,outline=TRUE,staplewex=.6)
    }
  }
  if(length(groups)>1) legend("topright",inset=c(-.36,0),legend=groups,col=cols,pch=16,bty="n",xpd=TRUE,cex=.9)
}
cairo_pdf(paste0(p$output,".pdf"),width=p$width_mm/25.4,height=p$height_mm/25.4,family="Arial",pointsize=11)
draw(); dev.off()
png(paste0(p$output,".png"),width=p$width_mm,height=p$height_mm,units="mm",res=300,bg="white",type=if(.Platform$OS.type=="windows") "windows" else "cairo",pointsize=11)
draw(); dev.off()
