import type { FC } from 'react';
import { Loader2, CheckCircle2, ScanText, Sparkles, QrCode, Database } from 'lucide-react';
import type { DocumentDetail } from '../types';

interface ProcessingProgressProps {
  document: DocumentDetail;
}

export const ProcessingProgress: FC<ProcessingProgressProps> = ({ document }) => {
  const percent = document.progress_percent || 0;
  const currentStep = document.current_step || 'Iniciando procesamiento...';
  const currentPage = document.current_page || 1;
  const totalPages = document.page_count || 1;

  // Real pipeline stages
  const stages = [
    { id: 'text', label: 'Extrayendo texto digital', icon: ScanText },
    { id: 'ocr', label: 'Ejecutando OCR inteligente y preprocesamiento', icon: ScanText },
    { id: 'vision', label: 'Analizando imágenes y elementos visuales', icon: Sparkles },
    { id: 'codes', label: 'Detectando códigos QR, barras, firmas y sellos', icon: QrCode },
    { id: 'index', label: 'Indexando contenido por página', icon: Database },
  ];

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 max-w-2xl mx-auto w-full">
      <div className="w-full bg-slate-900/80 border border-slate-800 rounded-2xl p-8 shadow-2xl backdrop-blur-md">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Procesando documento...</h3>
              <p className="text-xs text-slate-400 font-mono truncate max-w-sm" title={document.filename}>
                {document.filename}
              </p>
            </div>
          </div>
          <div className="text-right">
            <span className="text-2xl font-bold font-mono text-indigo-400">{percent}%</span>
            <p className="text-[11px] text-slate-400">
              Página {currentPage} de {totalPages}
            </p>
          </div>
        </div>

        {/* Real Progress Bar */}
        <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden mb-6 p-0.5 border border-slate-700/50">
          <div
            className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 rounded-full transition-all duration-300 shadow-sm shadow-indigo-500/50"
            style={{ width: `${percent}%` }}
          />
        </div>

        {/* Current Live Step */}
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 mb-6 flex items-center gap-2.5 text-xs text-slate-300">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
          <span className="font-medium text-slate-200">{currentStep}</span>
        </div>

        {/* Pipeline Checklist */}
        <div className="space-y-2 border-t border-slate-800 pt-5">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Flujo de análisis por página
          </p>
          <div className="grid grid-cols-1 gap-2 text-xs">
            {stages.map((stg) => (
              <div
                key={stg.id}
                className="flex items-center gap-2.5 text-slate-400 py-1"
              >
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{stg.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
