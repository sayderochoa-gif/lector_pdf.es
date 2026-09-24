import type { DocumentDetail, PageData, QueryResponse, SearchResponse } from '../types';

const API_BASE = '/api';

async function parseErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json();
    return data.detail || data.message || data.error || fallback;
  } catch {
    return fallback;
  }
}

export async function uploadDocument(file: File): Promise<DocumentDetail> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorMsg = await parseErrorMessage(res, 'Error al subir el documento PDF');
    throw new Error(errorMsg);
  }

  return res.json();
}

export async function getDocumentList(): Promise<DocumentDetail[]> {
  const res = await fetch(`${API_BASE}/documents`);
  if (!res.ok) {
    const errorMsg = await parseErrorMessage(res, 'Error al obtener la lista de documentos');
    throw new Error(errorMsg);
  }
  return res.json();
}

export async function getDocumentStatus(docId: string): Promise<DocumentDetail> {
  const res = await fetch(`${API_BASE}/documents/${docId}/status`);
  if (!res.ok) {
    const errorMsg = await parseErrorMessage(res, 'Error al obtener el estado del documento');
    throw new Error(errorMsg);
  }
  return res.json();
}

export async function getDocument(docId: string): Promise<DocumentDetail> {
  const res = await fetch(`${API_BASE}/documents/${docId}`);
  if (!res.ok) {
    const errorMsg = await parseErrorMessage(res, 'Error al obtener el documento');
    throw new Error(errorMsg);
  }
  return res.json();
}

export async function getPageData(docId: string, pageNum: number): Promise<PageData> {
  const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNum}`);
  if (!res.ok) {
    const errorMsg = await parseErrorMessage(res, `Error al obtener información de la página ${pageNum}`);
    throw new Error(errorMsg);
  }
  return res.json();
}

export function getPageImageUrl(docId: string, pageNum: number): string {
  return `${API_BASE}/documents/${docId}/pages/${pageNum}/image`;
}

export async function chatbotDocument(docId: string, query: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/documents/${docId}/chatbot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });

  if (!res.ok) {
    const errorMsg = await parseErrorMessage(res, 'Error al consultar el Chatbot (RAG)');
    throw new Error(errorMsg);
  }

  return res.json();
}

export async function chatDocument(docId: string, query: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/documents/${docId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });

  if (!res.ok) {
    const errorMsg = await parseErrorMessage(res, 'Error al consultar el Chat');
    throw new Error(errorMsg);
  }

  return res.json();
}

export async function queryDocument(docId: string, query: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/documents/${docId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });

  if (!res.ok) {
    const errorMsg = await parseErrorMessage(res, 'Error al consultar el documento');
    throw new Error(errorMsg);
  }

  return res.json();
}

export async function searchDocument(
  docId: string,
  query: string,
  exact: boolean = false,
  caseSensitive: boolean = false
): Promise<SearchResponse> {
  const params = new URLSearchParams({
    q: query,
    exact: exact ? 'true' : 'false',
    case_sensitive: caseSensitive ? 'true' : 'false',
  });

  const res = await fetch(`${API_BASE}/documents/${docId}/search?${params.toString()}`);
  if (!res.ok) {
    const errorMsg = await parseErrorMessage(res, 'Error al buscar en el documento');
    throw new Error(errorMsg);
  }

  return res.json();
}
