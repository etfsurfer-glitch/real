// 계약서 개인정보 로컬 마스킹 — 주민등록번호·법인등록번호·계좌번호를 **브라우저에서** 찾아 검게 가린 뒤
// 업로드한다. 서버는 마스킹된 파일만 받는다(원본의 고유식별정보가 서버로 전송되지 않음).
//
// 방식: tesseract.js(WASM OCR, kor)로 단어별 좌표를 얻고, 패턴에 걸린 단어 박스를 캔버스에서
// 검게 칠한다. PDF는 pdf.js로 페이지를 렌더 → 마스킹 → jsPDF로 재조립(JPEG). 이미지는 캔버스 재인코딩.
// 자산(worker/wasm/kor)은 /tess/* 자체 호스팅 — 외부 CDN 의존 없음, 업로드 시에만 지연 로드(~5MB, 1회 캐시).
//
// 실측 검증(2026-07-16, 실계약 20종 114페이지): 완전형(880102-1066114)·부분형(671208-1)·
// 별표형(820927-*******)·법인번호(110111-0013419) 전부 검출, 실번호 놓침 0(빈칸·양식문구 제외).
// 한계: OCR 기반이라 심한 손글씨·저해상도는 놓칠 수 있음 — 검출 0건이면 원본 그대로 업로드(품질 보존).
import { createWorker, type Worker } from "tesseract.js";
import { jsPDF } from "jspdf";

// 마스킹 패턴 — 과탐(계좌번호 앞부분 등)은 허용(민감정보라 가려서 손해 없음), 미탐 최소화가 목표.
const PATTERNS: RegExp[] = [
  /\d{6}\s*-\s*[\d*]{1,7}/g,  // 주민·법인 6-7 (부분기재 671208-1, 별표 820927-******* 포함)
  /(?<!\d)\d{13}(?!\d)/g,     // 하이픈 없이 붙여 쓴 13자리(경계 필수 — 14자리 중개등록번호·등기 일련번호 과탐 방지)
  /\d{6}\s+\d{7}/g,           // 하이픈이 공백으로 OCR된 경우
];

// 계좌번호 — 은행마다 형식이 달라(3-3-6·6-2-6·4-2-7·3-4-2-5·3-6-2-3…) 숫자만으론 과탐이 심함.
// 실계약 20종 실측: 계좌는 항상 "계좌·예금주·은행(뱅크)"과 같은 줄에 있음(16/16) — 사용자 지침대로
// 이 키워드 문맥에서만 적용한다. **전화번호는 절대 가리면 안 됨**(고객 연락처 추출에 필요):
// ①전화형(0XX-…)은 표 경계선이 숫자로 붙는 OCR 노이즈("1010-9872-1118")까지 감안해 제외
// ②최소 자릿수 10(실측 계좌 최소 11자리 — 02-XXX-XXXX 9자리 유선전화 자연 배제).
const ACCOUNT_LINE_KW = /계좌|예금주|은행|뱅크/;
const ACCOUNT_RES: RegExp[] = [
  /(?<!\d)\d{2,6}(?:-\d{2,7}){1,3}(?!\d)/g,  // 대시 그룹형(정규화 후라 대시 통일됨)
  /(?<!\d)\d{10,14}(?!\d)/g,                 // 계좌 키워드 줄에서 붙여 쓴 10~14자리
];
// 전화형(휴대폰 010/070·유선 02/0XX) — 앞에 노이즈 숫자 1자리가 붙어도 전화로 인식해 보존
const PHONE_RE = /^\d?0\d{1,2}-\d{3,4}-\d{4}$/;
const digitCount = (t: string) => (t.match(/\d/g) || []).length;

// 어느 단계든 멈추면 "계속 로딩"이 아니라 명확한 에러가 뜨도록 전 단계 타임아웃.
function withTimeout<T>(p: Promise<T>, ms: number, what: string): Promise<T> {
  return new Promise((res, rej) => {
    const t = setTimeout(() => rej(new Error(`${what} 단계가 ${Math.round(ms / 1000)}초를 초과했습니다. 새로고침(Ctrl+F5) 후 다시 시도해 주세요.`)), ms);
    p.then((v) => { clearTimeout(t); res(v); }, (e) => { clearTimeout(t); rej(e); });
  });
}

let _worker: Worker | null = null;
async function getWorker(): Promise<Worker> {
  if (_worker) return _worker;
  const w = await withTimeout(createWorker("kor", 1, {
    workerPath: "/tess/worker.min.js",
    corePath: "/tess/core",
    langPath: "/tess/lang",
  }), 60000, "개인정보 인식기 다운로드");
  _worker = w;
  return w;
}

type Box = { x0: number; y0: number; x1: number; y1: number };

// 캔버스 한 장을 OCR → 패턴 매칭 → 검정 박스. 가린 건수 반환.
async function maskCanvas(canvas: HTMLCanvasElement): Promise<number> {
  const worker = await getWorker();
  const { data } = await withTimeout(worker.recognize(canvas), 90000, "문서 인식");
  const ctx = canvas.getContext("2d")!;
  const done = new Set<string>();
  let n = 0;
  for (const line of (data as any).lines ?? []) {
    // 라인 텍스트를 단어 오프셋과 함께 재구성 — 매칭 구간에 걸친 단어 박스를 합쳐 가린다
    let text = "";
    const spans: { s: number; e: number; box: Box }[] = [];
    for (const w of line.words ?? []) {
      if (text) text += " ";
      const s = text.length;
      text += w.text || "";
      spans.push({ s, e: text.length, box: w.bbox });
    }
    const norm = text.replace(/[–—−‐‑]/g, "-");
    // 이 줄이 계좌 문맥이면 계좌 패턴도 함께 적용
    const res = ACCOUNT_LINE_KW.test(norm) ? [...PATTERNS, ...ACCOUNT_RES] : PATTERNS;
    for (const re of res) {
      re.lastIndex = 0;
      let m: RegExpExecArray | null;
      while ((m = re.exec(norm))) {
        if (ACCOUNT_RES.includes(re) && (digitCount(m[0]) < 10 || PHONE_RE.test(m[0]))) continue;
        const ms = m.index, me = ms + m[0].length;
        const hit = spans.filter((sp) => sp.e > ms && sp.s < me);
        if (!hit.length) continue;
        const x0 = Math.min(...hit.map((h) => h.box.x0)) - 4;
        const y0 = Math.min(...hit.map((h) => h.box.y0)) - 4;
        const x1 = Math.max(...hit.map((h) => h.box.x1)) + 4;
        const y1 = Math.max(...hit.map((h) => h.box.y1)) + 4;
        const key = `${x0},${y0},${x1},${y1}`;
        if (done.has(key)) continue;   // 여러 패턴이 같은 구간에 걸리면 1건으로
        done.add(key);
        ctx.fillStyle = "#000";
        ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
        n++;
      }
    }
  }
  return n;
}

async function imageToCanvas(file: File): Promise<HTMLCanvasElement> {
  // imageOrientation:"from-image" — 폰 카메라 사진의 EXIF 회전을 반영해 **똑바로 세워** 그린다.
  // (기본값 "none"이면 EXIF를 무시하고 원본 픽셀 그대로 그려, 옆으로 누운 계약서가 서버로 전송돼
  //  Gemini가 연도 등 숫자를 오독한다.) 옵션 미지원 브라우저는 무시하므로 안전.
  const bmp = await createImageBitmap(file, { imageOrientation: "from-image" })
    .catch(() => createImageBitmap(file).catch(() => null));
  if (!bmp) throw new Error("이미지를 읽을 수 없습니다. JPG·PNG 또는 PDF로 올려주세요 (HEIC는 미지원 브라우저가 있습니다).");
  const canvas = document.createElement("canvas");
  canvas.width = bmp.width; canvas.height = bmp.height;
  canvas.getContext("2d")!.drawImage(bmp, 0, 0);
  bmp.close();
  return canvas;
}

const toBlob = (c: HTMLCanvasElement, q = 0.9): Promise<Blob> =>
  new Promise((res, rej) => c.toBlob((b) => (b ? res(b) : rej(new Error("인코딩 실패"))), "image/jpeg", q));

export type MaskResult = { file: File; masked: number; pages: number };

/** 계약서 파일에서 주민·법인번호를 로컬 마스킹. 검출 0건이면 원본을 그대로 반환(품질 보존). */
export async function maskSensitiveDoc(
  file: File,
  onProgress?: (msg: string) => void,
): Promise<MaskResult> {
  const isPdf = (file.type === "application/pdf") || /\.pdf$/i.test(file.name);
  onProgress?.("개인정보 확인 준비 중… (최초 1회는 인식기 다운로드로 몇 초 더 걸립니다)");

  if (!isPdf) {
    const canvas = await imageToCanvas(file);
    onProgress?.("주민·법인·계좌번호 확인 중…");
    const masked = await maskCanvas(canvas);
    if (!masked) return { file, masked: 0, pages: 1 };
    const blob = await toBlob(canvas);
    return {
      file: new File([blob], file.name.replace(/\.[^.]+$/, "") + ".masked.jpg", { type: "image/jpeg" }),
      masked, pages: 1,
    };
  }

  // PDF — pdf.js는 무겁고 이 경로에서만 필요해서 동적 import(코드 스플릿)
  const pdfjs = await import("pdfjs-dist");
  const workerUrl = (await import("pdfjs-dist/build/pdf.worker.min.mjs?url")).default;
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
  const doc = await withTimeout(pdfjs.getDocument({ data: await file.arrayBuffer() }).promise, 30000, "PDF 열기");
  if (doc.numPages > 40) throw new Error(`페이지가 너무 많습니다(${doc.numPages}p). 계약서·확인설명서 부분만 나눠 올려주세요.`);

  let totalMasked = 0;
  const pageJpegs: { data: string; w: number; h: number }[] = [];
  for (let i = 1; i <= doc.numPages; i++) {
    onProgress?.(`주민·법인·계좌번호 확인 중… (${i}/${doc.numPages}페이지)`);
    const page = await doc.getPage(i);
    const base = page.getViewport({ scale: 1 });
    // OCR 검증(150DPI≈폭 1240px)과 같은 급 — 폭 ~1600px로 렌더
    const scale = Math.min(3, Math.max(1.5, 1600 / base.width));
    const vp = page.getViewport({ scale });
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(vp.width); canvas.height = Math.ceil(vp.height);
    await withTimeout(page.render({ canvasContext: canvas.getContext("2d")!, viewport: vp } as any).promise, 30000, "페이지 렌더");
    totalMasked += await maskCanvas(canvas);
    pageJpegs.push({ data: canvas.toDataURL("image/jpeg", 0.88), w: canvas.width, h: canvas.height });
  }

  if (!totalMasked) return { file, masked: 0, pages: doc.numPages };   // 원본 유지

  const pdf = new jsPDF({ unit: "px", format: [pageJpegs[0].w, pageJpegs[0].h], compress: true });
  pageJpegs.forEach((p, idx) => {
    if (idx > 0) pdf.addPage([p.w, p.h]);
    pdf.addImage(p.data, "JPEG", 0, 0, p.w, p.h);
  });
  const blob = pdf.output("blob");
  return {
    file: new File([blob], file.name.replace(/\.pdf$/i, "") + ".masked.pdf", { type: "application/pdf" }),
    masked: totalMasked, pages: doc.numPages,
  };
}
