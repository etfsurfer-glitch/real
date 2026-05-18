import { Link, Route, Routes } from "react-router-dom";
import Overview from "./pages/Overview";
import ComplexDetail from "./pages/ComplexDetail";
import Changes from "./pages/Changes";

export default function App() {
  return (
    <div className="layout">
      <header className="top">
        <h1>
          <Link to="/" style={{ color: "inherit" }}>네이버 부동산 추적기</Link>
        </h1>
        <nav style={{ fontSize: 13 }}>
          <Link to="/" style={{ marginRight: 12 }}>전체</Link>
          <Link to="/changes">가격 변동</Link>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/complex/:complexNo" element={<ComplexDetail />} />
        <Route path="/changes" element={<Changes />} />
      </Routes>
    </div>
  );
}
