import { BrowserRouter as Router, Route, Routes, Link } from "react-router-dom";
import PromptToImage from "./pages/prompt_to_image";

function About() {
  return (
    <div className="max-w-3xl mx-auto bg-amber-100/80 backdrop-blur rounded-xl shadow-lg border border-amber-500 p-6 mt-10 text-stone-800">
      <h1 className="text-3xl font-bold mb-4 text-amber-700">Về chúng tôi</h1>
      <p className="mb-2">
        <strong>Tác giả: </strong>Trần Phước Lộc - Sinh viên Đại Học Cần Thơ – Niên luận “Chuyển văn bản lịch sử phong kiến Việt Nam thành hình ảnh”.
      </p>
      <p className="mb-2">
        <strong>Tài liệu tham khảo:</strong> Việt Nam sử lược, Đại Việt sử ký toàn thư, Lịch sử Việt Nam, Lam Sơn thực lục, Ngàn năm áo mũ, Trang phục Việt Nam.
      </p>
      <p className="mb-2">
        <strong>Thư viện sử dụng:</strong> spaCy, PyVi, FastAPI, Stable Diffusion, TailwindCSS, React, Shadcn.
      </p>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      {/* Nền trống đồng xoay */}
      <div className="trongdong-bg"></div>

      {/* Nội dung */}
      <div className="content-overlay min-h-screen flex flex-col">
        {/* NAV */}
        <nav className="bg-black/70 backdrop-blur sticky top-0 z-50 border-b border-stone-700 shadow-md">
          <div className="max-w-6xl mx-auto flex justify-between items-center px-6 py-3">
            <div className="flex items-center gap-3">
              <img src="src/assets/trongdong.png" alt="Logo" className="h-9 w-9 rounded-full border border-stone-600" />
              <Link to="/" className="text-xl font-bold text-amber-400">
                VNHis2Image
              </Link>
            </div>
            <div className="flex gap-6 font-medium">
              <Link to="/" className="text-stone-200 hover:text-amber-400 transition-colors">Sinh ảnh</Link>
              <Link to="/about" className="text-stone-200 hover:text-amber-400 transition-colors">Giới thiệu</Link>
            </div>
          </div>
        </nav>

        {/* MAIN */}
        <main className="flex-grow flex justify-center items-start py-10 px-4">
          <div className="max-w-6xl w-full">
            <Routes>
              <Route path="/" element={<PromptToImage />} />
              <Route path="/about" element={<About />} />
            </Routes>
          </div>
        </main>

        {/* FOOTER */}
        <footer className="bg-black/70 border-t border-stone-700 py-6 text-center text-stone-300 text-sm shadow-inner">
          <div className="max-w-6xl mx-auto space-y-2">
            <p className="font-medium text-amber-400">© 2025 VNHis2Image — Niên luận ngành Khoa học máy tính</p>
            <p>B2105973 - Trần Phước Lộc</p>
            <div className="flex justify-center gap-4 text-xs">
              <a href="https://spacy.io" className="hover:text-amber-400" target="_blank">spaCy</a>
              <a href="https://pyvi.org" className="hover:text-amber-400" target="_blank">PyVi</a>
              <a href="https://tailwindcss.com" className="hover:text-amber-400" target="_blank">TailwindCSS</a>
              <a href="https://react.dev" className="hover:text-amber-400" target="_blank">React</a>
            </div>
          </div>
        </footer>
      </div>
    </Router>
  );
}
