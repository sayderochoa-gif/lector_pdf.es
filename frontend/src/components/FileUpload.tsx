import React, { useRef, useState } from 'react';
import { UploadCloud, CheckCircle2, Sparkles, AlertCircle } from 'lucide-react';

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  isUploading: boolean;
}

export const FileUpload: React.FC<FileUploadProps> = ({ onFileSelect, isUploading }) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndHandle = (file: File) => {
    setErrorMessage(null);
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setErrorMessage('Por favor seleccione un archivo en formato PDF (.pdf).');
      return;
    }
    if (file.size > 100 * 1024 * 1024) {
      setErrorMessage('El archivo excede el límite máximo de 100 MB.');
      return;
    }
    onFileSelect(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndHandle(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 max-w-4xl mx-auto w-full">
      {/* Hero Badge */}
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium mb-6">
        <Sparkles className="w-3.5 h-3.5" />
        Sistema Integral de Análisis Documental y Visión
      </div>

      <h2 className="text-3xl sm:text-4xl font-semibold text-white text-center tracking-tight mb-3">
        Cargue su documento PDF para análisis profundo
      </h2>
      <p className="text-slate-400 text-sm text-center max-w-xl mb-8">
        Procesamiento automático página a página: extracción de texto, OCR inteligente, detección de objetos visuales, códigos QR/barras, firmas y sellos.
      </p>

      {/* Drop Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        className={`w-full max-w-2xl border-2 border-dashed rounded-2xl p-10 flex flex-col items-center justify-center cursor-pointer transition-all duration-200 group relative overflow-hidden ${
          isDragOver
            ? 'border-indigo-500 bg-indigo-500/10 scale-[1.01]'
            : 'border-slate-800 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/70'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              validateAndHandle(e.target.files[0]);
            }
          }}
        />

        <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
          <UploadCloud className="w-8 h-8 text-indigo-400" />
        </div>

        <p className="text-base font-medium text-white mb-1 text-center">
          Arrastre y suelte su archivo PDF aquí, o haga clic para seleccionar
        </p>
        <p className="text-xs text-slate-400 text-center">
          Soporta PDFs digitales, escaneados o mixtos de 1 a 100+ páginas (hasta 100 MB)
        </p>

        {isUploading && (
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-xs font-medium text-slate-200">Subiendo archivo...</p>
            </div>
          </div>
        )}
      </div>

      {/* Error message if validation fails */}
      {errorMessage && (
        <div className="mt-4 flex items-center gap-2 px-4 py-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Capabilities Overview */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-10 w-full max-w-2xl text-xs text-slate-400">
        <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-900/30 border border-slate-800/60">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>OCR con Deskew & Filtros</span>
        </div>
        <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-900/30 border border-slate-800/60">
          <CheckCircle2 className="w-4 h-4 text-indigo-400 shrink-0" />
          <span>Visión: árboles, autos, personas</span>
        </div>
        <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-900/30 border border-slate-800/60">
          <CheckCircle2 className="w-4 h-4 text-amber-400 shrink-0" />
          <span>Firmas manuscritas & sellos</span>
        </div>
        <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-900/30 border border-slate-800/60">
          <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
          <span>Códigos QR & Barcodes 1D</span>
        </div>
      </div>
    </div>
  );
};
