import type { FC } from 'react';
import { FileText, Upload, Sparkles, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import type { DocumentDetail } from '../types';

interface HeaderProps {
  currentDoc: DocumentDetail | null;
  documents?: DocumentDetail[];
  onSelectDoc?: (doc: DocumentDetail) => void;
  onUploadClick: () => void;
  isProcessing: boolean;
}

export const Header: FC<HeaderProps> = ({
  currentDoc,
  documents = [],
  onSelectDoc,
  onUploadClick,
  isProcessing,
}) => {
  return (
    <header className="h-16 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-40">
      {/* Brand & Title */}
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/20 ring-1 ring-white/10">
          <FileText className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-semibold text-white tracking-tight">LectorPDF</h1>
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              OCR & Vision AI
            </span>
          </div>
          <p className="text-xs text-slate-400 hidden sm:block">
            Análisis documental, reconocimiento de texto y visión por computador
          </p>
        </div>
      </div>

      {/* Center: Current Document Info / Selector / Status Badge */}
      {currentDoc && (
        <div className="hidden md:flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs">
          {documents.length > 1 && onSelectDoc ? (
            <select
              value={currentDoc.id}
              onChange={(e) => {
                const selected = documents.find((d) => d.id === e.target.value);
                if (selected) onSelectDoc(selected);
              }}
              className="bg-slate-950 text-slate-200 border border-slate-700/80 rounded-md px-2 py-0.5 text-xs font-mono max-w-[220px] truncate focus:outline-none focus:border-indigo-500 cursor-pointer"
              title="Cambiar documento activo"
            >
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename} ({d.page_count} pág.)
                </option>
              ))}
            </select>
          ) : (
            <span className="text-slate-300 font-mono max-w-[200px] truncate" title={currentDoc.filename}>
              {currentDoc.filename}
            </span>
          )}

          <span className="text-slate-600">•</span>
          <span className="text-slate-400">
            {currentDoc.page_count} {currentDoc.page_count === 1 ? 'pág.' : 'págs.'}
          </span>
          <span className="text-slate-600">•</span>

          {currentDoc.status === 'completed' && (
            <span className="flex items-center gap-1 text-emerald-400 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Listo
            </span>
          )}
          {(currentDoc.status === 'processing' || currentDoc.status === 'pending') && (
            <span className="flex items-center gap-1 text-amber-400 font-medium">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {currentDoc.status === 'pending' ? 'En cola...' : `${currentDoc.progress_percent}%`}
            </span>
          )}
          {currentDoc.status === 'error' && (
            <span className="flex items-center gap-1 text-rose-400 font-medium">
              <AlertCircle className="w-3.5 h-3.5" />
              Error
            </span>
          )}
        </div>
      )}

      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={onUploadClick}
          disabled={isProcessing}
          className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white text-xs font-medium transition-all shadow-md shadow-indigo-600/20 disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
        >
          <Upload className="w-4 h-4" />
          <span>Cargar PDF</span>
        </button>
      </div>
    </header>
  );
};
