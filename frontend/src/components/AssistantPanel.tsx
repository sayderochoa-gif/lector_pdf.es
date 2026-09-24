import { useState, useEffect } from 'react';
import type { FC } from 'react';
import {
  Send,
  Bot,
  Search,
  MessageSquare,
  Eye,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Loader2,
  Sparkles,
} from 'lucide-react';
import type { QueryMatch, QueryResponse, SearchResponse } from '../types';
import { chatbotDocument, chatDocument, searchDocument } from '../services/api';
import { MatchCard } from './MatchCard';

interface AssistantPanelProps {
  docId: string;
  onNavigateToPage: (page: number, match?: QueryMatch) => void;
}

export const AssistantPanel: FC<AssistantPanelProps> = ({ docId, onNavigateToPage }) => {
  const [activeTab, setActiveTab] = useState<'chatbot' | 'chat' | 'search'>('chatbot');
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Chatbot (RAG con IA) Response state
  const [chatbotResponse, setChatbotResponse] = useState<QueryResponse | null>(null);

  // Chat (Preguntas directas) Response state
  const [chatResponse, setChatResponse] = useState<QueryResponse | null>(null);

  // Exact Text Search state
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [exactMatch, setExactMatch] = useState(false);
  const [caseSensitive, setCaseSensitive] = useState(false);

  useEffect(() => {
    setChatbotResponse(null);
    setChatResponse(null);
    setSearchResults(null);
    setErrorMessage(null);
    setInputQuery('');
  }, [docId]);

  const chatbotSuggestedQueries = [
    '¿El documento tiene firmas?',
    '¿Hay código QR en el documento?',
    '¿Hay código de barras dentro del documento?',
    '¿De qué trata este documento?',
    '¿Existe algún sello o estampa?',
    '¿Hay tablas estructuradas?',
    '¿Hay elementos visuales o fotografías?',
    '¿Qué información extrajo Tesseract OCR?',
  ];

  const chatSuggestedQueries = [
    '¿Cuántas páginas contienen la palabra factura?',
    '¿Qué contiene la página 1?',
    '¿Existe el número de identificación 123456789?',
    '¿En qué página aparece la palabra contrato?',
    'Buscar Bogotá',
    'Buscar NIT',
  ];

  const handleQuerySubmit = async (queryText?: string) => {
    const q = queryText || inputQuery;
    if (!q.trim()) return;

    setIsLoading(true);
    setErrorMessage(null);

    try {
      if (activeTab === 'chatbot') {
        const res = await chatbotDocument(docId, q);
        setChatbotResponse(res);
      } else if (activeTab === 'chat') {
        const res = await chatDocument(docId, q);
        setChatResponse(res);
      } else {
        const res = await searchDocument(docId, q, exactMatch, caseSensitive);
        setSearchResults(res);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Error al procesar la consulta');
    } finally {
      setIsLoading(false);
    }
  };

  const currentResponse = activeTab === 'chatbot' ? chatbotResponse : activeTab === 'chat' ? chatResponse : null;

  return (
    <div className="w-96 lg:w-[430px] border-l border-slate-800 bg-slate-950 flex flex-col h-full shrink-0">
      {/* Tabs */}
      <div className="h-12 border-b border-slate-800 px-3 flex items-center gap-1.5 select-none bg-slate-900/60">
        <button
          onClick={() => setActiveTab('chatbot')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            activeTab === 'chatbot'
              ? 'bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
          title="Chatbot con RAG e IA para preguntas complejas (firmas, QR, códigos de barras, semántica)"
        >
          <Bot className="w-3.5 h-3.5 text-indigo-200" />
          <span>Chatbot</span>
          <span className="text-[9px] px-1 py-0.2 bg-white/20 rounded font-semibold tracking-wider">RAG</span>
        </button>

        <button
          onClick={() => setActiveTab('chat')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            activeTab === 'chat'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
          title="Chat para preguntas directas, conteo de palabras, resumen de página y búsqueda léxica"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>Chat</span>
        </button>

        <button
          onClick={() => setActiveTab('search')}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            activeTab === 'search'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
          title="Búsqueda de texto literal con opciones avanzadas"
        >
          <Search className="w-3.5 h-3.5" />
          <span>Búsqueda</span>
        </button>
      </div>

      {/* Query Input Section */}
      <div className="p-4 border-b border-slate-800 space-y-3 bg-slate-900/40">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleQuerySubmit();
          }}
          className="relative flex items-center"
        >
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            placeholder={
              activeTab === 'chatbot'
                ? '¿El documento tiene firmas?, ¿Hay código QR?, ¿De qué trata?...'
                : activeTab === 'chat'
                ? '¿Cuántas páginas contienen la palabra X?, ¿Qué contiene la página 1?...'
                : 'Buscar palabra o frase exacta en el documento...'
            }
            className="w-full pl-3.5 pr-10 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors shadow-inner"
          />
          <button
            type="submit"
            disabled={isLoading || !inputQuery.trim()}
            className="absolute right-1.5 p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:pointer-events-none text-white transition-all cursor-pointer shadow"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>

        {/* Options for Text Search Tab */}
        {activeTab === 'search' && (
          <div className="flex items-center gap-4 text-[11px] text-slate-400 select-none">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={exactMatch}
                onChange={(e) => setExactMatch(e.target.checked)}
                className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0"
              />
              <span>Palabra completa</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={caseSensitive}
                onChange={(e) => setCaseSensitive(e.target.checked)}
                className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0"
              />
              <span>Distinguir mayúsculas</span>
            </label>
          </div>
        )}

        {/* Suggested Queries Chips */}
        {activeTab !== 'search' && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <p className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider">
                {activeTab === 'chatbot' ? 'Preguntas Complejas (RAG + IA)' : 'Consultas Rápidas (Chat)'}
              </p>
              {activeTab === 'chatbot' && (
                <span className="text-[10px] text-indigo-400 font-medium flex items-center gap-1">
                  <Sparkles className="w-2.5 h-2.5" /> Multimodal
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
              {(activeTab === 'chatbot' ? chatbotSuggestedQueries : chatSuggestedQueries).map((sq, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    setInputQuery(sq);
                    handleQuerySubmit(sq);
                  }}
                  className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-[11px] text-slate-300 hover:text-white hover:border-indigo-500/50 hover:bg-indigo-500/10 transition-all cursor-pointer text-left"
                >
                  {sq}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Results View Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {errorMessage && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Chatbot or Chat Results */}
        {(activeTab === 'chatbot' || activeTab === 'chat') && currentResponse && (
          <div className="space-y-4">
            {/* System Formatted Answer Card */}
            <div
              className={`rounded-xl p-4 border text-xs leading-relaxed space-y-3 ${
                currentResponse.found
                  ? currentResponse.status === 'found'
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-100'
                    : 'bg-amber-500/10 border-amber-500/30 text-amber-100'
                  : 'bg-slate-900/70 border-slate-800 text-slate-300'
              }`}
            >
              <div className="flex items-center justify-between font-semibold">
                <div className="flex items-center gap-2">
                  {currentResponse.found ? (
                    currentResponse.status === 'found' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    )
                  ) : (
                    <HelpCircle className="w-4 h-4 text-slate-400 shrink-0" />
                  )}
                  <span>
                    {activeTab === 'chatbot' ? 'Chatbot (RAG con IA)' : 'Chat (Respuesta Directa)'}
                  </span>
                </div>
                {activeTab === 'chatbot' && (
                  <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded-full border border-indigo-500/30">
                    RAG Multimodal
                  </span>
                )}
              </div>

              <div className="whitespace-pre-line font-sans font-medium text-slate-200">
                {currentResponse.explanation}
              </div>

              {/* Direct Jump Buttons for Pages */}
              {currentResponse.pages_found && currentResponse.pages_found.length > 0 && (
                <div className="pt-2 border-t border-white/10 flex flex-wrap gap-2">
                  {currentResponse.pages_found.map((p) => (
                    <button
                      key={p}
                      onClick={() => onNavigateToPage(p)}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-medium transition-all cursor-pointer shadow-sm"
                    >
                      <Eye className="w-3 h-3" />
                      <span>[Ver página {p}]</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Individual Matches List */}
            {currentResponse.matches && currentResponse.matches.length > 0 && (
              <div className="space-y-2">
                <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Detalles de coincidencias ({currentResponse.matches.length})
                </p>
                {currentResponse.matches.map((match, idx) => (
                  <MatchCard
                    key={idx}
                    match={match}
                    onViewPage={onNavigateToPage}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Text Search Tab Results */}
        {activeTab === 'search' && searchResults && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-400 pb-1 border-b border-slate-800">
              <span>Resultados para "{searchResults.query}"</span>
              <span className="font-mono text-indigo-400 font-semibold">
                {searchResults.total_matches} coincidencia(s)
              </span>
            </div>

            {searchResults.matches.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-xs">
                No se encontraron coincidencias exactas para este término.
              </div>
            ) : (
              searchResults.matches.map((match, idx) => (
                <MatchCard
                  key={idx}
                  match={match}
                  onViewPage={onNavigateToPage}
                />
              ))
            )}
          </div>
        )}

        {/* Empty state when no query has been run yet */}
        {!currentResponse && !searchResults && !isLoading && (
          <div className="flex flex-col items-center justify-center h-64 text-center text-slate-500 gap-2 p-6">
            {activeTab === 'chatbot' ? (
              <>
                <Bot className="w-8 h-8 text-indigo-500 mb-1" />
                <p className="text-xs font-medium text-slate-300">Chatbot con RAG e IA</p>
                <p className="text-[11px] text-slate-500 max-w-xs">
                  Especializado en preguntas complejas: firmas manuscritas, códigos QR decodificados, códigos de barras, sellos y síntesis semántica profunda.
                </p>
              </>
            ) : activeTab === 'chat' ? (
              <>
                <MessageSquare className="w-8 h-8 text-indigo-400 mb-1" />
                <p className="text-xs font-medium text-slate-300">Chat Rápido</p>
                <p className="text-[11px] text-slate-500 max-w-xs">
                  Consultas directas: conteo de palabras en páginas, búsqueda de NIT o identificadores, y contenido de páginas específicas.
                </p>
              </>
            ) : (
              <>
                <Search className="w-8 h-8 text-slate-600 mb-1" />
                <p className="text-xs font-medium text-slate-300">Búsqueda Literal</p>
                <p className="text-[11px] text-slate-500 max-w-xs">
                  Búsqueda exacta de términos y frases en todo el documento.
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
