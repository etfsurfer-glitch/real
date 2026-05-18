import { Link, Route, Routes } from "react-router-dom";
import Overview from "./pages/Overview";
import ComplexDetail from "./pages/ComplexDetail";

export default function App() {
  return (
    <div className="layout">
      <header className="top">
        <h1>
          <Link to="/" style={{ color: "inherit" }}>네이버 부동산 추적기</Link>
        </h1>
        <span className="sub">서초동 · 일별 스냅샷</span>
      </header>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/complex/:complexNo" element={<ComplexDetail />} />
      </Routes>
    </div>
  );
}
