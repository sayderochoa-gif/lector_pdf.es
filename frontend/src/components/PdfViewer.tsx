import { useState, useEffect, useRef } from 'react';
import type { FC, FormEvent } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Layers,
  Info,
} from 'lucide-react';
import type { BoundingBox, PageData } from '../types';
import { getPageImageUrl } from '../services/api';

export interface HighlightBox {
  bbox: BoundingBox;
  label: string;
  type: string;
  confidence?: number;
}

interface PdfViewerProps {
  docId: string;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  pageData?: PageData | null;
  activeHighlights?: HighlightBox[];
}

export const PdfViewer: FC<PdfViewerProps> = ({
  docId,
  currentPage,
  totalPages,
  onPageChange,
  pageData,
  activeHighlights = [],
}) => {
  const [zoom, setZoom] = useState(100);
  const [pageInput, setPageInput] = useState(String(currentPage));
  const [showOverlays, setShowOverlays] = useState(true);
  const [hoveredBox, setHoveredBox] = useState<HighlightBox | null>(null);
  const [isImageLoading, setIsImageLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setPageInput(String(currentPage));
    setIsImageLoading(true);
  }, [currentPage, docId]);

  const handlePrevPage = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  const handlePageInputSubmit = (e: FormEvent) => {
    e.preventDefault();
    const p = parseInt(pageInput, 10);
    if (!isNaN(p) && p >= 1 && p <= totalPages) {
      onPageChange(p);
    } else {
      setPageInput(String(currentPage));
    }
  };

  const handleZoomIn = () => setZoom((prev) => Math.min(250, prev + 25));
  const handleZoomOut = () => setZoom((prev) => Math.max(50, prev - 25));
  const handleResetZoom = () => setZoom(100);

  // Compile all detections on this page for interactive overlay
  const pageDetections: HighlightBox[] = [];

  if (pageData && showOverlays) {
    // QR codes
    pageData.qr_codes.forEach((qr) => {
      if (qr.bbox) pageDetections.push({ bbox: qr.bbox, label: qr.label, type: 'qr', confidence: qr.confidence });
    });
    // Barcodes
    pageData.barcodes.forEach((bc) => {
      if (bc.bbox) pageDetections.push({ bbox: bc.bbox, label: bc.label, type: 'barcode', confidence: bc.confidence });
    });
    // Signatures
    pageData.signatures.forEach((sig) => {
      if (sig.bbox) pageDetections.push({ bbox: sig.bbox, label: sig.label, type: 'signature', confidence: sig.confidence });
    });
    // Stamps
    pageData.stamps.forEach((st) => {
      if (st.bbox) pageDetections.push({ bbox: st.bbox, label: st.label, type: 'stamp', confidence: st.confidence });
    });
    // Tables
    pageData.tables.forEach((tb) => {
      if (tb.bbox) pageDetections.push({ bbox: tb.bbox, label: tb.label, type: 'table', confidence: tb.confidence });
    });
    // Visual objects
    pageData.objects.forEach((ob) => {
      if (ob.bbox) pageDetections.push({ bbox: ob.bbox, label: ob.label, type: 'visual', confidence: ob.confidence });
    });
  }

  // Merge activeHighlights for search terms
  activeHighlights.forEach((h) => {
    if (h.bbox) pageDetections.push(h);
  });

  const getOverlayColor = (type: string) => {
    switch (type) {
      case 'qr':
        return 'border-emerald-500 bg-emerald-500/15 text-emerald-300';
      case 'barcode':
        return 'border-teal-500 bg-teal-500/15 text-teal-300';
      case 'signature':
        return 'border-purple-500 bg-purple-500/20 text-purple-300';
      case 'stamp':
        return 'border-rose-500 bg-rose-500/20 text-rose-300';
      case 'table':
        return 'border-blue-500 bg-blue-500/15 text-blue-300';
      case 'visual':
        return 'border-amber-500 bg-amber-500/20 text-amber-300';
      default:
        return 'border-indigo-500 bg-indigo-500/25 text-indigo-300';
    }
  };

  const imageUrl = getPageImageUrl(docId, currentPage);

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950/60 overflow-hidden relative">
      {/* Top Toolbar */}
      <div className="h-12 border-b border-slate-800 bg-slate-900/60 px-4 flex items-center justify-between gap-3 text-xs select-none">
        {/* Navigation */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={handlePrevPage}
            disabled={currentPage <= 1}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
            title="Página anterior"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <form onSubmit={handlePageInputSubmit} className="flex items-center gap-1">
            <span className="text-slate-400">Pág.</span>
            <input
              type="text"
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              onBlur={() => setPageInput(String(currentPage))}
              className="w-10 px-1.5 py-0.5 text-center bg-slate-950 border border-slate-800 rounded font-mono text-white text-xs focus:outline-none focus:border-indigo-500"
            />
            <span className="text-slate-500 font-mono">/ {totalPages}</span>
          </form>

          <button
            onClick={handleNextPage}
            disabled={currentPage >= totalPages}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
            title="Página siguiente"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Zoom & Overlay Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowOverlays(!showOverlays)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors cursor-pointer ${
              showOverlays
                ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400'
                : 'bg-slate-800/40 border-slate-700/50 text-slate-400'
            }`}
            title="Mostrar/ocultar capas de detección"
          >
            <Layers className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Detecciones</span>
          </button>

          <div className="h-4 w-px bg-slate-800" />

          <button
            onClick={handleZoomOut}
            disabled={zoom <= 50}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-40 cursor-pointer"
            title="Reducir zoom"
          >
            <ZoomOut className="w-4 h-4" />
          </button>

          <span className="font-mono text-slate-400 w-10 text-center">{zoom}%</span>

          <button
            onClick={handleZoomIn}
            disabled={zoom >= 250}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-40 cursor-pointer"
            title="Aumentar zoom"
          >
            <ZoomIn className="w-4 h-4" />
          </button>

          <button
            onClick={handleResetZoom}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
            title="Restablecer tamaño normal (100%)"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Page Image Display Area with Pan & Overlays */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-6 flex items-start justify-center relative bg-slate-950/90"
      >
        <div
          className="relative shadow-2xl rounded-lg overflow-hidden border border-slate-800 transition-transform duration-100 ease-out origin-top"
          style={{ width: `${zoom}%`, maxWidth: zoom <= 100 ? '900px' : 'none' }}
        >
          {/* High-res rendered page */}
          {isImageLoading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-900/30 backdrop-blur-[1px]">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          <img
            src={imageUrl}
            alt={`Página ${currentPage}`}
            className={`w-full h-auto block select-none bg-white transition-opacity duration-150 ${isImageLoading ? 'opacity-60' : 'opacity-100'}`}
            loading="lazy"
            onLoad={() => setIsImageLoading(false)}
            onError={() => setIsImageLoading(false)}
          />

          {/* Interactive Bounding Box Highlights */}
          {showOverlays && (
            <div className="absolute inset-0 pointer-events-none">
              {pageDetections.map((det, idx) => {
                const box = det.bbox;
                if (!box) return null;

                const left = `${box.x * 100}%`;
                const top = `${box.y * 100}%`;
                const width = `${box.width * 100}%`;
                const height = `${box.height * 100}%`;
                const colorClasses = getOverlayColor(det.type);

                return (
                  <div
                    key={`det-${idx}`}
                    onMouseEnter={() => setHoveredBox(det)}
                    onMouseLeave={() => setHoveredBox(null)}
                    style={{ left, top, width, height }}
                    className={`absolute border-2 rounded-md transition-all duration-150 pointer-events-auto cursor-pointer ${colorClasses} hover:ring-2 hover:ring-white/40`}
                  >
                    <span className="absolute -top-5 left-0 px-1.5 py-0.2 rounded text-[10px] font-medium bg-slate-900/90 border border-slate-700 text-slate-200 whitespace-nowrap shadow-sm pointer-events-none">
                      {det.label} {det.confidence ? `(${(det.confidence * 100).toFixed(0)}%)` : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Bottom status indicator */}
      <div className="h-8 border-t border-slate-800 bg-slate-900/70 px-4 flex items-center justify-between text-[11px] text-slate-400 select-none">
        <div className="flex items-center gap-3">
          <span>
            {pageData?.ocr_applied ? (
              <span className="text-amber-400 font-medium">Página procesada con OCR</span>
            ) : pageData?.has_text_layer ? (
              <span className="text-emerald-400 font-medium">Texto digital nativo</span>
            ) : (
              'Analizada'
            )}
          </span>
          {pageDetections.length > 0 && (
            <span className="text-slate-500">
              • {pageDetections.length} elemento(s) detectado(s) en esta página
            </span>
          )}
        </div>

        {hoveredBox && (
          <div className="flex items-center gap-1.5 text-indigo-300">
            <Info className="w-3.5 h-3.5" />
            <span>{hoveredBox.label} ({hoveredBox.type})</span>
          </div>
        )}
      </div>
    </div>
  );
};
