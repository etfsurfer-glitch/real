import { useState } from "react";

/** 드롭다운을 바꿔도 즉시 refetch 하지 않고 '적용'을 눌러야 URL(=쿼리)이 갱신되게 한다.
 *  - build(): 현재 필터 상태로 만든 URL (없으면 null)
 *  - 반환 url: 마지막으로 '적용'된 URL — useFetchJson 등에 그대로 넘긴다.
 *  - dirty: 현재 설정이 적용본과 달라 '적용' 대기 중인지.
 *  - apply(): 현재 설정을 적용(=fetch 트리거). */
export function useDeferredUrl(build: () => string | null) {
  const draft = build();
  const [applied, setApplied] = useState<string | null>(draft);
  return {
    url: applied,
    dirty: draft !== applied,
    apply: () => setApplied(draft),
  };
}

/** 필터바 끝에 두는 '적용' 버튼. 변경분이 있을 때만(=dirty) 활성화/강조. */
export function ApplyButton({ dirty, onApply }: { dirty: boolean; onApply: () => void }) {
  return (
    <button type="button" className="apply-btn" disabled={!dirty} onClick={onApply}>
      적용
    </button>
  );
}
