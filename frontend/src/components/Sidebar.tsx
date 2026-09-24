import type { FC } from 'react';
import {
  FileText,
  ScanText,
  QrCode,
  Barcode,
  PenTool,
  Stamp,
  Table as TableIcon,
  Image as ImageIcon,
  Sparkles,
  Layers,
  ChevronRight,
  HardDrive,
  Calendar,
} from 'lucide-react';
import type { DocumentDetail } from '../types';

interface SidebarProps {
  document: DocumentDetail | null;
  activePage: number;
  onPageSelect: (page: number) => void;
  pageThumbnailsCount?: number;
}

export const Sidebar: FC<SidebarProps> = ({
  document,
  activePage,
  onPageSelect,
}) => {
  if (!document) {
    return (
      <aside className="w-72 border-r border-slate-800 bg-slate-950 p-5 flex flex-col gap-6 select-none hidden lg:flex">
        <div className="flex flex-col items-center justify-center h-64 text-center text-slate-500 gap-2 border border-dashed border-slate-800 rounded-xl p-4">
          <FileText className="w-8 h-8 text-slate-600 mb-1" />
          <p className="text-xs font-medium">Ningún documento cargado</p>
          <p className="text-[11px] text-slate-600">Suba un PDF para ver información y métricas</p>
        </div>
      </aside>
    );
  }

  const formatFileSize = (bytes?: number): string => {
    if (!bytes || isNaN(bytes)) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDate = (isoStr?: string): string => {
    if (!isoStr) return 'Reciente';
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return 'Reciente';
      return d.toLocaleDateString('es-ES', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return 'Reciente';
    }
  };

  const counts = document.summary_counts || {
    text_pages: 0,
    ocr_pages: 0,
    qr_codes: 0,
    barcodes: 0,
    signatures: 0,
    stamps: 0,
    images: 0,
    tables: 0,
    visual_objects: 0,
  };

  return (
    <aside className="w-80 border-r border-slate-800 bg-slate-950/70 p-4 flex flex-col gap-5 overflow-y-auto hidden md:flex shrink-0">
      {/* Document Information Card */}
      <div className="rounded-xl bg-slate-900/60 border border-slate-800/80 p-3.5 space-y-3">
        <div className="flex items-center gap-2 text-slate-200 font-medium text-xs border-b border-slate-800 pb-2">
          <FileText className="w-4 h-4 text-indigo-400" />
          <span className="truncate" title={document.filename}>
            {document.filename}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400">
          <div className="flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-slate-500" />
            <span>Páginas: <strong className="text-slate-200">{document.page_count}</strong></span>
          </div>
          <div className="flex items-center gap-1.5">
            <HardDrive className="w-3.5 h-3.5 text-slate-500" />
            <span>Tamaño: <strong className="text-slate-200">{formatFileSize(document.filesize)}</strong></span>
          </div>
          <div className="col-span-2 flex items-center gap-1.5 text-slate-500">
            <Calendar className="w-3.5 h-3.5 text-slate-500" />
            <span>Cargado: <span className="text-slate-400">{formatDate(document.created_at)}</span></span>
          </div>
        </div>

        {/* PyMuPDF Validation Badge */}
        <div className="pt-2 border-t border-slate-800/80 flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Validación PyMuPDF
            </span>
            {document.document_type === 'imagen' ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <ScanText className="w-3 h-3" />
                Imagen / OCR
              </span>
            ) : document.document_type === 'texto' ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-sky-500/10 text-sky-400 border border-sky-500/20">
                <FileText className="w-3 h-3" />
                Texto Digital
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
                <Layers className="w-3 h-3" />
                Mixto
              </span>
            )}
          </div>
          {document.validation_details && (
            <p className="text-[10px] text-slate-500 leading-tight">
              {document.validation_details}
            </p>
          )}
        </div>
      </div>

      {/* Analysis Badges Grid */}
      <div className="space-y-2">
        <h3 className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          Análisis del Documento
        </h3>

        <div className="grid grid-cols-2 gap-1.5 text-xs">
          {/* Digital Text */}
          <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/40 border border-slate-800/60">
            <span className="flex items-center gap-1.5 text-slate-300">
              <FileText className="w-3.5 h-3.5 text-sky-400" />
              Texto digital
            </span>
            <span className="font-semibold text-sky-400 font-mono text-[11px]">
              {counts.text_pages}
            </span>
          </div>

          {/* OCR */}
          <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/40 border border-slate-800/60">
            <span className="flex items-center gap-1.5 text-slate-300">
              <ScanText className="w-3.5 h-3.5 text-amber-400" />
              OCR
            </span>
            <span className="font-semibold text-amber-400 font-mono text-[11px]">
              {counts.ocr_pages}
            </span>
          </div>

          {/* QR Codes */}
          <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/40 border border-slate-800/60">
            <span className="flex items-center gap-1.5 text-slate-300">
              <QrCode className="w-3.5 h-3.5 text-emerald-400" />
              Códigos QR
            </span>
            <span className="font-semibold text-emerald-400 font-mono text-[11px]">
              {counts.qr_codes}
            </span>
          </div>

          {/* Barcodes */}
          <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/40 border border-slate-800/60">
            <span className="flex items-center gap-1.5 text-slate-300">
              <Barcode className="w-3.5 h-3.5 text-teal-400" />
              Barras
            </span>
            <span className="font-semibold text-teal-400 font-mono text-[11px]">
              {counts.barcodes}
            </span>
          </div>

          {/* Signatures */}
          <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/40 border border-slate-800/60">
            <span className="flex items-center gap-1.5 text-slate-300">
              <PenTool className="w-3.5 h-3.5 text-purple-400" />
              Firmas
            </span>
            <span className="font-semibold text-purple-400 font-mono text-[11px]">
              {counts.signatures}
            </span>
          </div>

          {/* Stamps */}
          <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/40 border border-slate-800/60">
            <span className="flex items-center gap-1.5 text-slate-300">
              <Stamp className="w-3.5 h-3.5 text-rose-400" />
              Sellos
            </span>
            <span className="font-semibold text-rose-400 font-mono text-[11px]">
              {counts.stamps}
            </span>
          </div>

          {/* Tables */}
          <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/40 border border-slate-800/60">
            <span className="flex items-center gap-1.5 text-slate-300">
              <TableIcon className="w-3.5 h-3.5 text-blue-400" />
              Tablas
            </span>
            <span className="font-semibold text-blue-400 font-mono text-[11px]">
              {counts.tables}
            </span>
          </div>

          {/* Images & Visual Objects */}
          <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/40 border border-slate-800/60">
            <span className="flex items-center gap-1.5 text-slate-300">
              <ImageIcon className="w-3.5 h-3.5 text-orange-400" />
              Visual
            </span>
            <span className="font-semibold text-orange-400 font-mono text-[11px]">
              {counts.images + counts.visual_objects}
            </span>
          </div>
        </div>
      </div>

      {/* Pages Navigator */}
      <div className="flex-1 flex flex-col min-h-0 space-y-2">
        <h3 className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase flex items-center justify-between">
          <span>Páginas ({document.page_count})</span>
          <span className="text-[10px] text-slate-500 font-normal">Click para navegar</span>
        </h3>

        <div className="flex-1 overflow-y-auto space-y-1 pr-1 border border-slate-800/60 rounded-xl p-1.5 bg-slate-900/30">
          {Array.from({ length: document.page_count }, (_, i) => i + 1).map((pageNum) => {
            const isSelected = pageNum === activePage;
            const isReady =
              document.status === 'completed' || pageNum <= (document.current_page || 0);

            return (
              <button
                key={pageNum}
                onClick={() => onPageSelect(pageNum)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-indigo-600 text-white font-medium shadow-sm'
                    : isReady
                    ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                    : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/40 opacity-75'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-5 h-5 rounded flex items-center justify-center text-[11px] font-mono ${
                      isSelected
                        ? 'bg-indigo-700 text-white'
                        : isReady
                        ? 'bg-slate-800 text-slate-300'
                        : 'bg-slate-900 text-slate-600 border border-slate-800'
                    }`}
                  >
                    {pageNum}
                  </span>
                  <span>Página {pageNum}</span>
                </div>
                {isReady ? (
                  <ChevronRight className={`w-3.5 h-3.5 ${isSelected ? 'text-white' : 'text-slate-600'}`} />
                ) : (
                  <span className="text-[10px] text-indigo-400/80 animate-pulse font-mono">en cola</span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
};
