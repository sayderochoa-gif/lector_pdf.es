import { useState, useEffect, useRef, useCallback } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { FileUpload } from './components/FileUpload';
import { ProcessingProgress } from './components/ProcessingProgress';
import { PdfViewer } from './components/PdfViewer';
import type { HighlightBox } from './components/PdfViewer';
import { AssistantPanel } from './components/AssistantPanel';
import type { DocumentDetail, PageData, QueryMatch } from './types';
import { getDocumentList, getDocumentStatus, getPageData, uploadDocument } from './services/api';

export function App() {
  const [currentDoc, setCurrentDoc] = useState<DocumentDetail | null>(null);
  const [documents, setDocuments] = useState<DocumentDetail[]>([]);
  const [activePage, setActivePage] = useState<number>(1);
  const [currentPageData, setCurrentPageData] = useState<PageData | null>(null);
  const [activeHighlights, setActiveHighlights] = useState<HighlightBox[]>([]);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  // Poll processing status
  const pollingRef = useRef<number | null>(null);

  // Refresh document list and optionally keep a selected doc
  const refreshDocs = useCallback(async (selectDocId?: string) => {
    try {
      const docs = await getDocumentList();
      setDocuments(docs);
      if (selectDocId) {
        const found = docs.find((d) => d.id === selectDocId);
        if (found) setCurrentDoc(found);
      } else if (docs.length > 0) {
        setCurrentDoc((prev) => prev || docs[0]);
      }
    } catch (err) {
      console.error('Error loading documents list:', err);
    }
  }, []);

  useEffect(() => {
    refreshDocs();
  }, [refreshDocs]);

  // Poll status while document is pending or processing
  useEffect(() => {
    if (currentDoc && (currentDoc.status === 'processing' || currentDoc.status === 'pending')) {
      pollingRef.current = window.setInterval(async () => {
        try {
          const updated = await getDocumentStatus(currentDoc.id);
          setCurrentDoc(updated);
          if (updated.status === 'completed' || updated.status === 'error') {
            if (pollingRef.current !== null) {
              window.clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
            refreshDocs(updated.id);
          }
        } catch (err) {
          console.error('Error polling document status:', err);
        }
      }, 400);
    }

    return () => {
      if (pollingRef.current !== null) {
        window.clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [currentDoc?.id, currentDoc?.status, refreshDocs]);

  // Load page data whenever activePage or document progress updates
  useEffect(() => {
    if (
      currentDoc &&
      (currentDoc.status === 'completed' || (currentDoc.status === 'processing' && (currentDoc.current_page || 0) >= activePage))
    ) {
      const loadPage = async () => {
        try {
          const pData = await getPageData(currentDoc.id, activePage);
          setCurrentPageData(pData);
        } catch (err) {
          console.error(`Error loading page data for page ${activePage}:`, err);
        }
      };
      loadPage();
    } else {
      setCurrentPageData(null);
    }
  }, [currentDoc?.id, currentDoc?.status, currentDoc?.current_page, activePage]);

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    setGlobalError(null);
    try {
      const doc = await uploadDocument(file);
      setCurrentDoc(doc);
      setActivePage(1);
      setActiveHighlights([]);
      setShowUploadModal(false);
      refreshDocs(doc.id);
    } catch (err: any) {
      setGlobalError(err.message || 'Error al subir el archivo');
    } finally {
      setIsUploading(false);
    }
  };

  const handlePageSelect = (page: number, match?: QueryMatch) => {
    setActivePage(page);
    if (match?.bbox) {
      setActiveHighlights([
        {
          bbox: match.bbox,
          label: match.label,
          type: match.type,
          confidence: match.confidence,
        },
      ]);
    } else {
      setActiveHighlights([]);
    }
  };

  const handleDocumentChange = (doc: DocumentDetail) => {
    setCurrentDoc(doc);
    setActivePage(1);
    setActiveHighlights([]);
  };

  // Determine if document is ready for progressive studio viewing
  const isStudioReady =
    currentDoc &&
    !showUploadModal &&
    (currentDoc.status === 'completed' ||
      (currentDoc.status === 'processing' && (currentDoc.current_page || 0) >= 1));

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans select-none">
      {/* Top Header */}
      <Header
        currentDoc={currentDoc}
        documents={documents}
        onSelectDoc={handleDocumentChange}
        onUploadClick={() => setShowUploadModal(true)}
        isProcessing={currentDoc?.status === 'processing' || currentDoc?.status === 'pending'}
      />

      {/* Main Workspace */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        {/* Background Processing Banner (Progressive Loading) */}
        {isStudioReady && currentDoc.status === 'processing' && (
          <div className="bg-gradient-to-r from-indigo-950/90 via-slate-900/90 to-indigo-950/90 border-b border-indigo-500/30 px-4 py-1.5 flex items-center justify-between text-xs backdrop-blur-sm z-30 shrink-0 shadow-sm">
            <div className="flex items-center gap-2.5 text-indigo-200">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
              <span className="font-semibold text-white">Carga automatizada en segundo plano:</span>
              <span className="text-slate-300 truncate max-w-md">
                {currentDoc.current_step || `Indexando páginas (${currentDoc.current_page}/${currentDoc.page_count})...`}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-36 h-2 bg-slate-800 rounded-full overflow-hidden border border-indigo-500/20">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 rounded-full transition-all duration-300"
                  style={{ width: `${currentDoc.progress_percent}%` }}
                />
              </div>
              <span className="font-mono text-emerald-400 font-semibold text-[11px]">
                {currentDoc.progress_percent}%
              </span>
            </div>
          </div>
        )}

        <div className="flex-1 flex overflow-hidden relative">
          {/* State 1: No document loaded or upload modal active */}
          {(!currentDoc || showUploadModal) && (
            <div className={`${showUploadModal ? 'absolute inset-0 z-50 bg-slate-950/95 backdrop-blur-md flex items-center justify-center p-4' : 'flex-1 flex'}`}>
              <div className="w-full flex flex-col items-center">
                {showUploadModal && (
                  <div className="w-full max-w-2xl flex justify-end mb-2">
                    <button
                      onClick={() => setShowUploadModal(false)}
                      className="text-xs text-slate-400 hover:text-white px-3 py-1 rounded-lg bg-slate-900 border border-slate-800 cursor-pointer"
                    >
                      Cerrar
                    </button>
                  </div>
                )}
                <FileUpload onFileSelect={handleFileUpload} isUploading={isUploading} />
                {globalError && (
                  <p className="mt-4 text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 px-4 py-2 rounded-lg">
                    {globalError}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* State 2: Document is queued or preparing initial Page 1 */}
          {currentDoc &&
            !isStudioReady &&
            (currentDoc.status === 'processing' || currentDoc.status === 'pending') &&
            !showUploadModal && (
              <ProcessingProgress document={currentDoc} />
            )}

          {/* State 3: Document processed with error */}
          {currentDoc && currentDoc.status === 'error' && !showUploadModal && (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
              <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center mb-4 text-rose-400">
                ⚠️
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">Error en el análisis del documento</h3>
              <p className="text-xs text-slate-400 max-w-md mb-6">{currentDoc.error_message}</p>
              <button
                onClick={() => setShowUploadModal(true)}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium cursor-pointer"
              >
                Intentar con otro archivo
              </button>
            </div>
          )}

          {/* State 4: Progressive Studio View (Live when Page 1 is ready or completed) */}
          {isStudioReady && (
            <>
              {/* Left Sidebar */}
              <Sidebar
                document={currentDoc}
                activePage={activePage}
                onPageSelect={handlePageSelect}
              />

              {/* Center: PDF Viewer */}
              <PdfViewer
                docId={currentDoc.id}
                currentPage={activePage}
                totalPages={currentDoc.page_count}
                onPageChange={handlePageSelect}
                pageData={currentPageData}
                activeHighlights={activeHighlights}
              />

              {/* Right: AI Assistant & Search Panel */}
              <AssistantPanel
                docId={currentDoc.id}
                onNavigateToPage={handlePageSelect}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
