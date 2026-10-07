# 5개 단지 전용84 매매 호가 — 세제발표(2026-08-03 18시) 전후
import pyarrow.parquet as pq, statistics as st, json
ARC="/mnt/cold/archive/listings"
BEFORE="2026-08-02"; AFTER="2026-08-20"
CXS=[("104917","마포래미안푸르지오","마포 아현"),
     ("110938","e편한세상옥수파크힐스","성동 옥수"),
     ("100692","래미안옥수리버젠","성동 옥수"),
     ("114335","마포아이파크포레","마포 신수"),
     ("155817","올림픽파크포레온","강동 둔촌")]
COLS=["article_no","complex_no","trade_type","area2_m2","deal_or_warrant_price"]
def load(date):
    f=f"{ARC}/{date[:4]}/{date[5:7]}/listings_{date}.parquet"
    t=pq.read_table(f, columns=COLS)
    d=t.to_pydict()
    # cx -> {article_no: price(만원)}
    out={cx[0]:{} for cx in CXS}
    cxset=set(out)
    an,cn,tt,a2,pr=d["article_no"],d["complex_no"],d["trade_type"],d["area2_m2"],d["deal_or_warrant_price"]
    for i in range(len(an)):
        c=str(cn[i])
        if c not in cxset: continue
        if tt[i] not in ("A1","매매"): continue         # 매매만
        if a2[i] is None or abs(a2[i]-84.0)>0.5: continue  # 전용84
        p=pr[i]
        if not p: continue
        out[c][str(an[i])]=p/10000.0                     # 만원
    return out
B=load(BEFORE); A=load(AFTER)
def won(man):  # 만원 -> "X억 Y,ZZZ" 축약
    eok=int(man//10000); rem=int(round(man-eok*10000))
    return f"{eok}억{rem:,}" if eok else f"{rem:,}만"
res=[]
for cid,nm,loc in CXS:
    b=B[cid]; a=A[cid]
    bp=list(b.values()); ap=list(a.values())
    common=set(b)&set(a)
    chgs=[(a[k]-b[k]) for k in common]
    pcts=[(a[k]-b[k])/b[k]*100 for k in common if b[k]]
    cut=sum(1 for x in chgs if x<-0.5); frz=sum(1 for x in chgs if abs(x)<=0.5); up=sum(1 for x in chgs if x>0.5)
    r={"단지":nm,"위치":loc,
       "전_매물수":len(bp),"후_매물수":len(ap),
       "전_평균":round(st.mean(bp)) if bp else None,"후_평균":round(st.mean(ap)) if ap else None,
       "전_중앙":round(st.median(bp)) if bp else None,"후_중앙":round(st.median(ap)) if ap else None,
       "전_최저":round(min(bp)) if bp else None,"후_최저":round(min(ap)) if ap else None,
       "패널_n":len(common),
       "패널_평균변동액":round(st.mean(chgs)) if chgs else None,
       "패널_평균변동률":round(st.mean(pcts),2) if pcts else None,
       "패널_인하":cut,"패널_동결":frz,"패널_인상":up,
       "패널_평균인하폭":round(st.mean([x for x in chgs if x<-0.5])) if cut else None}
    res.append(r)
    print(f"\n■ {nm} ({loc})  전용84 매매")
    print(f"  발표전({BEFORE}) 매물 {r['전_매물수']}건  평균 {won(r['전_평균']) if r['전_평균'] else '-'}  중앙 {won(r['전_중앙']) if r['전_중앙'] else '-'}  최저 {won(r['전_최저']) if r['전_최저'] else '-'}")
    print(f"  발표후({AFTER}) 매물 {r['후_매물수']}건  평균 {won(r['후_평균']) if r['후_평균'] else '-'}  중앙 {won(r['후_중앙']) if r['후_중앙'] else '-'}  최저 {won(r['후_최저']) if r['후_최저'] else '-'}")
    if r['전_평균'] and r['후_평균']:
        dlv=r['후_평균']-r['전_평균']; dpc=dlv/r['전_평균']*100
        print(f"  평균호가 변동: {dlv:+,}만원 ({dpc:+.1f}%)  |  최저호가 변동: {(r['후_최저']-r['전_최저']):+,}만원")
    print(f"  [동일물건 패널 {r['패널_n']}건] 평균 {r['패널_평균변동액']:+}만 ({r['패널_평균변동률']:+}%)  인하 {r['패널_인하']}·동결 {r['패널_동결']}·인상 {r['패널_인상']}  평균인하폭 {r['패널_평균인하폭']}만" if r['패널_n'] else "  [패널] 공통 물건 없음")
# JSON 덤프(보고서 작성용)
print("\n===JSON===")
print(json.dumps({"before":BEFORE,"after":AFTER,"rows":res}, ensure_ascii=False))
