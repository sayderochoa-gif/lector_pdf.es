export type DetectionType =
  | 'text'
  | 'visual'
  | 'qr_code'
  | 'barcode'
  | 'signature'
  | 'stamp'
  | 'table'
  | 'diagram'
  | 'logo'
  | 'photo';

export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'error';

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  page_width?: number;
  page_height?: number;
}

export interface VisualDetection {
  id: string;
  type: DetectionType;
  label: string;
  confidence: number;
  bbox?: BoundingBox;
  metadata?: Record<string, any>;
}

export interface PageData {
  page: number;
  width: number;
  height: number;
  text: string;
  has_text_layer: boolean;
  ocr_applied: boolean;
  page_type?: 'imagen' | 'texto' | string;
  extracted_by?: 'tesseract' | 'pymupdf' | string;
  opencv_review?: Record<string, any>;
  objects: VisualDetection[];
  qr_codes: VisualDetection[];
  barcodes: VisualDetection[];
  signatures: VisualDetection[];
  stamps: VisualDetection[];
  images: VisualDetection[];
  tables: VisualDetection[];
  confidence: Record<string, number>;
  image_url: string;
}

export interface DocumentSummaryCounts {
  document_type?: string;
  validation_status?: string;
  validation_details?: string;
  text_pages: number;
  ocr_pages: number;
  qr_codes: number;
  barcodes: number;
  signatures: number;
  stamps: number;
  images: number;
  tables: number;
  visual_objects: number;
}

export interface DocumentDetail {
  id: string;
  filename: string;
  filesize: number;
  page_count: number;
  status: DocumentStatus;
  document_type?: 'imagen' | 'texto' | 'mixto' | 'desconocido' | string;
  validation_details?: string | null;
  current_page: number;
  current_step: string;
  progress_percent: number;
  created_at: string;
  updated_at: string;
  error_message?: string | null;
  summary_counts: DocumentSummaryCounts;
}

export interface QueryMatch {
  page: number;
  type: string;
  confidence: number;
  label: string;
  snippet?: string;
  bbox?: BoundingBox;
  metadata?: Record<string, any>;
}

export interface QueryResponse {
  found: boolean;
  status: 'found' | 'possible' | 'not_found';
  query: string;
  intent: string;
  explanation: string;
  matches: QueryMatch[];
  total_matches: number;
  pages_found: number[];
}

export interface SearchResponse {
  query: string;
  total_matches: number;
  matches: QueryMatch[];
}
