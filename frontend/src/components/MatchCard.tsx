import type { FC } from 'react';
import { Eye, CheckCircle2, AlertTriangle, FileText, Sparkles, QrCode, Barcode, PenTool, Stamp, Table } from 'lucide-react';
import type { QueryMatch } from '../types';

interface MatchCardProps {
  match: QueryMatch;
  searchTerm?: string;
  onViewPage: (pageNum: number, match?: QueryMatch) => void;
}

export const MatchCard: FC<MatchCardProps> = ({ match, onViewPage }) => {
  const getTypeBadge = (type: string) => {
    switch (type) {
      case 'text':
        return {
          label: 'Texto',
          color: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
          icon: FileText,
        };
      case 'visual':
      case 'photo':
        return {
          label: 'Visual / Imagen',
          color: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
          icon: Sparkles,
        };
      case 'qr':
      case 'qr_code':
        return {
          label: 'Código QR',
          color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
          icon: QrCode,
        };
      case 'barcode':
        return {
          label: 'Código de Barras',
          color: 'bg-teal-500/10 text-teal-400 border-teal-500/20',
          icon: Barcode,
        };
      case 'signature':
        return {
          label: 'Firma',
          color: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
          icon: PenTool,
        };
      case 'stamp':
        return {
          label: 'Sello / Estampa',
          color: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
          icon: Stamp,
        };
      case 'table':
        return {
          label: 'Tabla',
          color: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
          icon: Table,
        };
      default:
        return {
          label: type,
          color: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
          icon: Sparkles,
        };
    }
  };

  const badge = getTypeBadge(match.type);
  const Icon = badge.icon;
  const isHighConfidence = match.confidence >= 0.8;
  const confPercent = Math.round(match.confidence * 100);

  return (
    <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-4 space-y-3 transition-all hover:border-slate-700/80 hover:bg-slate-900/90 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {isHighConfidence ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          )}
          <span className="text-xs font-semibold text-slate-200">
            {isHighConfidence ? 'Coincidencia encontrada' : 'Posible coincidencia'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-medium ${badge.color}`}>
            <Icon className="w-3 h-3" />
            {badge.label}
          </span>
          <span className="text-[10px] font-mono text-slate-400">
            {confPercent}%
          </span>
        </div>
      </div>

      {/* Label / Term */}
      <div>
        <p className="text-sm font-medium text-white">{match.label}</p>
        <p className="text-xs text-indigo-400 font-mono mt-0.5">Página {match.page}</p>
      </div>

      {/* Snippet / Context */}
      {match.snippet && (
        <div className="rounded-lg bg-slate-950/70 border border-slate-800/80 p-2.5 text-xs text-slate-300 font-mono italic leading-relaxed">
          {match.snippet}
        </div>
      )}

      {/* Action button: Ver página */}
      <div className="flex justify-end pt-1">
        <button
          onClick={() => onViewPage(match.page, match)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-medium transition-all hover:scale-102 active:scale-98 cursor-pointer"
        >
          <Eye className="w-3.5 h-3.5" />
          <span>Ver página {match.page}</span>
        </button>
      </div>
    </div>
  );
};
