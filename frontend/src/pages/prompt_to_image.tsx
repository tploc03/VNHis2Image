/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable no-empty */
 
/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useMemo, useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Copy, Image as ImageIcon, Sparkles, Wand2 } from "lucide-react";

const PROMPT_TEMPLATES: Record<string, string> = {
  portrait:
    "A historically accurate portrait of [person] from the [dynasty] dynasty ([time]).\nAttire: [costume], accessories if any: [artifact]. Title(s): [title]. Organization: [organization]. Setting hints: [architecture], [location], with symbolic flora/fauna: [flora_fauna].\nDepict key traits: [concept].\nStyle: Vietnamese feudal history, museum-grade realism, mid-shot, natural lighting.\nAvoid anachronisms. No modern objects.\n",
  battle:
    "A realistic, historically grounded battle scene of [event] ([time]) led by [person] ([title]) belonging to [organization].\nArmor/garments: [costume]. Battlefield: [location], with weapons/artifacts: [artifact], environment includes [flora_fauna].\nMain actions: [action].\nCinematic lighting, dynamic composition, Vietnamese feudal realism, no modern elements.\n",
  architecture:
    "A detailed depiction of [architecture] from the [dynasty] dynasty ([time]) in [location].\nInclude related artifacts: [artifact], cultural motifs, flora/fauna: [flora_fauna].\nEmphasize proportions, materials, roof curvature, ornament patterns.\nStyle: Vietnamese feudal history, documentary realism, no modern objects.\n",
};

const REQUIRED_FIELDS: Record<string, string[]> = {
  portrait: ["person", "dynasty", "time", "costume"],
  battle: ["event", "time", "person", "title", "organization", "costume", "location", "action"],
  architecture: ["architecture", "dynasty", "time", "location"],
};

const PLACEHOLDER_REGEX = /\[([a-zA-Z0-9_]+)\]/g;
function extractPlaceholders(template: string): string[] {
  const fields = new Set<string>();
  let m: RegExpExecArray | null;
  while ((m = PLACEHOLDER_REGEX.exec(template))) fields.add(m[1]);
  return Array.from(fields);
}

const PLACEHOLDER_HINTS: Record<string, string> = {
  person: "vd: Lý Thường Kiệt",
  dynasty: "vd: Lý, Trần, Lê…",
  time: "vd: thế kỷ XI, năm 1075",
  costume: "vd: mũ binh, áo giáp vảy cá",
  artifact: "vd: kiếm, giáo, trống đồng",
  title: "vd: Thái úy, Hưng Đạo Vương",
  organization: "vd: quân Đại Việt, triều đình Lý",
  architecture: "vd: Khuê Văn Các, cổng thành",
  location: "vd: Thăng Long, sông Như Nguyệt",
  flora_fauna: "vd: tre, trúc, hạc, rồng",
  concept: "vd: dũng cảm, mưu lược, liêm chính",
  event: "vd: Trận Như Nguyệt",
  action: "vd: xung phong, bày trận mai phục",
};

type ProgressResp = {
  progress?: number;      // 0..1
  percent?: number;       // 0..100
  eta_seconds?: number;   // remaining seconds
  has_preview?: boolean;
  preview_b64?: string;   // optional base64
};

const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8001";

async function callNERAPI(text: string, style: string) {
  const r = await fetch(`${API_BASE}/ner`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, style }),
  });
  if (!r.ok) throw new Error(`NER API lỗi (${r.status})`);
  const data = await r.json();

  if (data?.fields) {
    return { fields: data.fields as Record<string, string>, scores: (data.scores || {}) as Record<string, number> };
  }
  if (Array.isArray(data?.spans)) {
    const fields: Record<string, string> = {};
    const scores: Record<string, number> = {};
    for (const sp of data.spans) {
      const label = String(sp.label || "").toLowerCase();
      const text = String(sp.text || "");
      const sc = typeof sp.score === "number" ? sp.score : undefined;
      if (!fields[label] || text.length > fields[label].length) {
        fields[label] = text;
        if (typeof sc === "number") scores[label] = sc;
      }
    }
    return { fields, scores };
  }

  return { fields: {}, scores: {} };
}

async function callImageAPI(prompt: string, signal?: AbortSignal): Promise<string> {
  const r = await fetch(`${API_BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
    signal,
  });
  if (!r.ok) throw new Error(`Generate API lỗi (${r.status})`);
  const data = await r.json();
  const b64 = data.image_base64 || (Array.isArray(data.images) ? data.images[0] : null);
  const url = data.image_url || data.url;
  if (b64 && typeof b64 === "string") return b64.startsWith("data:image") ? b64 : `data:image/png;base64,${b64}`;
  if (url) return url;
  throw new Error("Phản hồi /generate không có ảnh.");
}

async function callProgress(): Promise<ProgressResp> {
  const r = await fetch(`${API_BASE}/progress`);
  if (!r.ok) throw new Error(`Progress API lỗi (${r.status})`);
  return (await r.json()) as ProgressResp;
}

/** ------------ Component ------------ **/
export default function PromptToImage() {
  const [style, setStyle] = useState<keyof typeof PROMPT_TEMPLATES>("portrait");
  const [composeVietnamese, setComposeVietnamese] = useState(true);

  const controllerRef = useRef<AbortController | null>(null);

  const template = PROMPT_TEMPLATES[style];
  const placeholders = useMemo(() => extractPlaceholders(template), [template]);

  const [extraNotes, setExtraNotes] = useState("");
  const [generatedPrompt, setGeneratedPrompt] = useState("");
  const [imgUrl, setImgUrl] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [mode, setMode] = useState<"form" | "manual">("form");
  const [values, setValues] = useState<Record<string, string>>({});
  const [manualPrompt, setManualPrompt] = useState("");
  const [extracted, setExtracted] = useState<Record<string, string>>({});
  const [analysisNotes, setAnalysisNotes] = useState<string[]>([]);

  // progress states
  const [progressPct, setProgressPct] = useState(0);
  const [eta, setEta] = useState<number | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  const handleChange = (name: string, val: string) => setValues((prev) => ({ ...prev, [name]: val }));

  const buildPromptFromValues = (vals: Record<string, string>) => {
    let out = template;
    for (const f of placeholders) {
      const v = (vals[f] || "").trim();
      out = out.replaceAll(`[${f}]`, v || `[${f}]`);
    }
    if (extraNotes.trim()) out += `\nAdditional notes: ${extraNotes.trim()}\n`;
    out += `\nLanguage: ${composeVietnamese ? "Vietnamese" : "English"}.\n`;
    setGeneratedPrompt(out.trim());
    return out.trim();
  };

  const missingRequired = (vals: Record<string, string>) =>
    REQUIRED_FIELDS[style].filter((k) => !vals[k] || !vals[k].trim());

  const analyzeManual = async () => {
    setError(null);
    setAnalysisNotes([]);
    const base = manualPrompt.trim();
    if (!base) {
      setAnalysisNotes(["Chưa nhập prompt."]);
      return;
    }
    try {
      const res = await callNERAPI(base, style);
      const fields = res?.fields ?? {};
      setExtracted(fields);
      const miss = missingRequired(fields);
      setAnalysisNotes(miss.length ? miss.map((m) => `Thiếu trường bắt buộc: ${m}`) : ["Đủ trường bắt buộc theo phong cách."]);
    } catch (e: any) {
      setError(e.message || String(e));
    }
  };

  const handleGenerate = async () => {
    setError(null);
    setLoading(true);
    setImgUrl("");
    setProgressPct(0);
    setEta(null);
    setPreview(null);

    try {
      let finalPrompt = "";
      if (mode === "form") {
        const miss = missingRequired(values);
        if (miss.length) throw new Error(`Thiếu: ${miss.join(", ")}`);
        finalPrompt = buildPromptFromValues(values);
      } else {
        let vals = extracted;
        if (!Object.keys(vals).length) {
          const { fields } = await callNERAPI(manualPrompt, style);
          vals = fields;
          setExtracted(fields);
        }
        const miss = missingRequired(vals);
        if (miss.length) throw new Error(`Thiếu: ${miss.join(", ")}`);
        finalPrompt = buildPromptFromValues(vals);
      }

      controllerRef.current = new AbortController();
      try {
        const url = await callImageAPI(finalPrompt, controllerRef.current.signal);
        setImgUrl(url);
      } catch (e: any) {
        if (e?.name !== "AbortError") {
          setError(e.message || String(e));
          setImgUrl("");
        }
      }
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
      setProgressPct(0);
      setEta(null);
      setPreview(null);
    }
  };

  const copyPrompt = async () => {
    const p = generatedPrompt || (mode === "form" ? buildPromptFromValues(values) : buildPromptFromValues(extracted));
    if (p) await navigator.clipboard.writeText(p);
  };

  // Poll progress khi loading
  useEffect(() => {
    if (!loading) return;

    let timer: number | null = null;
    const tick = async () => {
      try {
        const p = await callProgress();
        const pct = typeof p.percent === "number" ? p.percent : (typeof p.progress === "number" ? p.progress * 100 : 0);
        setProgressPct(isFinite(pct) ? pct : 0);
        setEta(Number.isFinite(p.eta_seconds as number) ? (p.eta_seconds as number) : null);

        if (p.has_preview && p.preview_b64) {
          const prefixed = p.preview_b64.startsWith("data:image")
            ? p.preview_b64
            : `data:image/png;base64,${p.preview_b64}`;
          setPreview(prefixed);
        }
      } catch {
        // bỏ qua lỗi poll
      }
    };

    tick();
    timer = window.setInterval(tick, 700);
    return () => {
      if (timer) window.clearInterval(timer);
    };
  }, [loading]);

  const guidanceList = (
    <ul className="list-disc pl-5 space-y-1 text-sm text-stone-400">
      {REQUIRED_FIELDS[style].map((f) => (
        <li key={f}>
          Cần có <span className="font-mono text-amber-400">[{f}]</span>
          {PLACEHOLDER_HINTS[f] ? <span className="text-stone-500"> — {PLACEHOLDER_HINTS[f]}</span> : null}
        </li>
      ))}
    </ul>
  );

  return (
    <div className="min-h-screen w-full p-6">
      <div className="max-w-6xl mx-auto grid lg:grid-cols-2 gap-6">
        {/* Left */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <Card className="bg-stone-950/40 backdrop-blur border border-amber-700 shadow-[0_0_0_1px_rgba(168,137,26,0.2)]">
            <CardHeader>
              <CardTitle className="text-2xl font-bold text-amber-400">Chuyển văn bản lịch sử → Ảnh</CardTitle>
              <p className="text-sm text-stone-400">Chọn phong cách và chế độ nhập (Form hoặc Prompt tự do).</p>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid sm:grid-cols-2 gap-3 items-end">
                <div>
                  <Label className="text-stone-300">Phong cách ảnh</Label>
                  <Select
                    value={style}
                    onValueChange={(v: any) => {
                      setStyle(v as any);
                      setValues({});
                      setExtracted({});
                      setGeneratedPrompt("");
                      setImgUrl("");
                      setAnalysisNotes([]);
                    }}
                  >
                    <SelectTrigger className="mt-1 bg-stone-900 border-amber-700 text-stone-200">
                      <SelectValue placeholder="Chọn phong cách" />
                    </SelectTrigger>
                    <SelectContent className="bg-stone-900 border-amber-700 text-stone-200">
                      <SelectItem value="portrait">Portrait (Chân dung)</SelectItem>
                      <SelectItem value="battle">Battle (Trận đánh)</SelectItem>
                      <SelectItem value="architecture">Architecture (Kiến trúc)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex gap-3 items-center mt-6 sm:mt-0">
                  <Switch
                    checked={composeVietnamese}
                    onCheckedChange={setComposeVietnamese}
                    // className="h-6 w-11 data-[state=checked]:bg-amber-600 data-[state=unchecked]:bg-stone-600 shadow-inner"
                  />
                  {/* <span className="text-sm text-stone-300">Sinh prompt bằng tiếng Việt</span> */}
                </div>
              </div>

              {/* Mode switch */}
              <Tabs value={mode} onValueChange={(v: any) => setMode(v as any)} className="w-full">
                <TabsList className="bg-stone-900 border border-amber-700 text-stone-200">
                  <TabsTrigger value="form">Điền theo template</TabsTrigger>
                  <TabsTrigger value="manual">Nhập prompt tự do</TabsTrigger>
                </TabsList>

                {/* FORM MODE */}
                <TabsContent value="form" className="pt-4 space-y-4">
                    {/*<div className="rounded-xl border border-amber-700 p-3 bg-stone-900/60">
                    <p className="text-sm text-stone-300 mb-2">
                      Điền các chỗ <span className="font-mono text-amber-400">[placeholder]</span> bắt buộc:
                    </p>
                    {guidanceList}
                  </div>
                  */}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {placeholders.map((f) => {
                        const isRequired = REQUIRED_FIELDS[style].includes(f); // <- đánh dấu bắt buộc
                        return (
                          <div className="space-y-1" key={f}>
                            <Label className="capitalize text-stone-300">
                              {f.replaceAll("_", " ")}
                              {isRequired && <span className="text-red-500">&nbsp;*</span>}
                            </Label>
                            <Input
                              className="bg-stone-900 border-amber-700 placeholder:text-stone-500 text-stone-100"
                              placeholder={PLACEHOLDER_HINTS?.[f] || f}
                              value={values[f] || ""}
                              onChange={(e) => handleChange(f, e.target.value)}
                            />
                          </div>
                        );
                      })}
                    </div>
                  </TabsContent>

                {/* MANUAL MODE */}
                <TabsContent value="manual" className="pt-4 space-y-4">
                  <div className="rounded-xl border border-amber-700 p-3 bg-stone-900/60 space-y-2">
                    <div className="flex items-center gap-2 text-sm text-stone-300">
                      <Wand2 className="h-4 w-4 text-amber-400" />
                      <span>
                        Nhập prompt tự do, nhưng cần đủ nhãn bắt buộc cho phong cách{" "}
                        <Badge variant="secondary" className="bg-stone-800 border border-amber-700 text-amber-300">
                          {style}
                        </Badge>.
                      </span>
                    </div>
                    {guidanceList}
                  </div>

                  <div className="space-y-1">
                    <Label className="text-stone-300">Prompt của bạn</Label>
                    <Textarea
                      className="bg-stone-900 border-amber-700 min-h-[140px] placeholder:text-stone-500 text-stone-100"
                      placeholder={`Ví dụ (portrait): Chân dung Lý Thường Kiệt thời nhà Lý, thế kỷ XI, mặc áo giáp vảy cá và đội mũ binh…`}
                      value={manualPrompt}
                      onChange={(e: { target: { value: React.SetStateAction<string> } }) => setManualPrompt(e.target.value)}
                    />
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      variant="secondary"
                      onClick={analyzeManual}
                      className="gap-2 bg-amber-500 hover:bg-amber-400 text-stone-900 border border-amber-700"
                    >
                      <Wand2 className="h-4 w-4" /> Phân tích prompt (NER)
                    </Button>
                    {analysisNotes.map((w, i) => (
                      <span key={i} className={`text-xs ${w.startsWith("Thiếu") ? "text-red-400" : "text-emerald-400"}`}>
                        • {w}
                      </span>
                    ))}
                  </div>

                  {Object.keys(extracted).length > 0 && (
                    <div className="space-y-2">
                      <Label className="text-stone-300">Giá trị trích xuất (có thể chỉnh sửa)</Label>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {placeholders.map((f) => (
                          <div className="space-y-1" key={f}>
                            <Label className="capitalize text-stone-300">{f.replaceAll("_", " ")}</Label>
                            <Input
                              className="bg-stone-900 border-amber-700 placeholder:text-stone-500 text-stone-100"
                              value={extracted[f] || ""}
                              placeholder={PLACEHOLDER_HINTS[f] || f}
                              onChange={(e: { target: { value: any } }) => setExtracted((p) => ({ ...p, [f]: e.target.value }))}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </TabsContent>
              </Tabs>

              {/* Actions */}
              <div className="flex gap-3">
                <Button onClick={handleGenerate} disabled={loading} className="gap-2 bg-amber-600 hover:bg-amber-500 text-stone-900">
                  <Sparkles className="h-4 w-4" />
                  {loading ? "Đang sinh ảnh…" : "Sinh ảnh"}
                </Button>

                {loading ? (
                  <Button
                    variant="secondary"
                    onClick={async () => {
                      setError(null);
                      try { await fetch(`${API_BASE}/interrupt`, { method: "POST" }); } catch {}
                      try { controllerRef.current?.abort(); } catch {}
                      setLoading(false);
                    }}
                    className="gap-2 bg-stone-900 hover:bg-stone-800 text-amber-300 border border-amber-700"
                  >
                    Hủy tạo
                  </Button>
                ) : (
                  <Button variant="secondary" onClick={copyPrompt} className="gap-2 bg-stone-200 hover:bg-stone-300 text-stone-900">
                    <Copy className="h-4 w-4" />
                    Sao chép prompt
                  </Button>
                )}
              </div>

              {error && <div className="text-xs text-red-400">{error}</div>}

              {generatedPrompt && (
                <div className="space-y-2">
                  <Label className="text-stone-300">Prompt đã tạo</Label>
                  <Textarea readOnly className="bg-stone-900 border-amber-700 min-h-[140px] text-stone-100" value={generatedPrompt} />
                  <p className="text-xs text-stone-500">Kiểm tra thời gian/triều đại, tránh vật dụng hiện đại.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Right */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <Card className="bg-stone-950/40 backdrop-blur border border-amber-700 shadow-[0_0_0_1px_rgba(168,137,26,0.2)]">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-amber-400">
                <ImageIcon className="h-5 w-5" />
                Xem trước
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {loading && (
                <div className="space-y-2">
                  <div className="w-full bg-stone-900 rounded-full h-3 overflow-hidden border border-amber-700">
                    <div
                      className="bg-amber-500 h-3 transition-all"
                      style={{ width: `${Math.min(100, Math.max(0, progressPct))}%` }}
                    />
                  </div>
                  <div className="text-xs text-stone-400">
                    Tiến độ: <span className="text-amber-400 font-semibold">{progressPct.toFixed(1)}%</span>
                    {eta !== null && <> • Ước còn <span className="text-amber-400 font-semibold">{eta}s</span></>}
                  </div>
                  {preview && (
                    <img
                      src={preview}
                      alt="Xem trước"
                      className="w-full rounded-xl border border-amber-700"
                    />
                  )}
                </div>
              )}

              {imgUrl && !loading && (
                <motion.img
                  key={imgUrl}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  alt="Generated"
                  src={imgUrl}
                  className="w-full rounded-2xl border-4 border-amber-700 shadow-lg object-cover"
                />
              )}

              {/* <div className="text-xs text-stone-400 leading-relaxed space-y-1"> */}
                {/* <p className="mb-1">Cấu hình nhanh:</p>
                <ol className="list-decimal list-inside space-y-1">
                  <li>FE: <code>.env.development → VITE_API_BASE=http://localhost:8001</code></li>
                  <li>BE: cung cấp <code>POST /ner</code>, <code>POST /generate</code>, <code>GET /progress</code>, <code>POST /interrupt</code></li>
                  <li>Backend trả <code>{`{ image_base64 }`}</code> hoặc <code>{`{ image_url }`}</code></li>
                </ol>
              </div> */}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
