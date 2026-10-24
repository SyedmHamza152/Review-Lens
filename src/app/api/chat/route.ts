import { NextResponse } from "next/server";
import ZAI from "z-ai-web-dev-sdk";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = "http://127.0.0.1:8317";

interface ChatBody {
  jobId?: string;
  question?: string;
}

/** Compact, token-bounded evidence package from the Python report. */
function buildContext(report: any, reviews: any[]): string {
  const v = report.verdict;
  const t = report.totals;
  const lines: string[] = [];
  lines.push(`PRODUCT: ${report.job.product_name}`);
  lines.push(`DESCRIPTION: ${report.job.description ?? "n/a"}`);
  lines.push(`DATA_MODE: ${report.job.data_mode} (sample = synthetic demonstration data, NOT real reviews)`);
  lines.push(
    `VERDICT: ${v.label} | score ${v.score}/100 | positive ${v.positive_pct}% | negative ${v.negative_pct}% | neutral ${v.neutral_pct}% | mixed ${v.mixed_pct}% | analyzed ${t.analyzed} comments`,
  );
  lines.push(`PLATFORM COVERAGE: ${t.platforms_with_data}/${t.platforms_requested} platforms with data; ${t.spam_filtered} spam filtered`);
  lines.push(`LANGUAGES: ${report.languages.map((l: any) => `${l.language} ${l.count}`).join(", ")}`);

  if (report.comparison?.length) {
    lines.push("PLATFORM COMPARISON (name: n, pos%, neg%, mix%, avg_rating, top_complaint):");
    for (const c of report.comparison.slice(0, 12)) {
      lines.push(
        `- ${c.platform_name}: n=${c.total}, pos=${c.positive_pct}%, neg=${c.negative_pct}%, mixed=${c.mixed_pct}%, rating=${c.avg_rating ?? "n/a"}, low_sample=${c.low_sample}, top_complaint=${c.top_complaint_aspect ?? "n/a"}`,
      );
    }
  }
  if (report.aspects?.length) {
    lines.push("ASPECTS (aspect: mentions, pos, neg):");
    for (const a of report.aspects.slice(0, 11)) {
      lines.push(`- ${a.label}: ${a.mentions} (+${a.positive}/-${a.negative}), scope=${a.scope}`);
    }
  }
  if (report.advantages?.length) {
    lines.push(`TOP ADVANTAGES: ${report.advantages.map((a: any) => `${a.phrase} (${a.count}x)`).join("; ")}`);
  }
  if (report.complaints?.length) {
    lines.push(`TOP COMPLAINTS: ${report.complaints.map((c: any) => `${c.phrase} (${c.count}x)`).join("; ")}`);
  }
  if (reviews.length) {
    lines.push("REPRESENTATIVE COMMENTS (verbatim, with platform | language | sentiment | rating):");
    for (const r of reviews) {
      lines.push(`- [${r.platform} | ${r.language} | ${r.sentiment} | rating=${r.rating ?? "n/a"}] "${r.text_original.slice(0, 220)}"`);
    }
  }
  lines.push(
    "REMINDERS: sentiment percentages describe the collected sample only, not the market; " +
    "sample-size caveats apply (low_sample=true platforms are unreliable for ranking); " +
    "if DATA_MODE includes sample data, say so when giving platform-specific claims.",
  );
  return lines.join("\n");
}

export async function POST(req: Request) {
  let body: ChatBody;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const jobId = (body.jobId ?? "").trim();
  const question = (body.question ?? "").trim();
  if (!jobId || !question) {
    return NextResponse.json({ error: "jobId and question are required" }, { status: 400 });
  }
  if (question.length > 1000) {
    return NextResponse.json({ error: "Question too long" }, { status: 413 });
  }

  try {
    const reportRes = await fetch(`${BACKEND}/api/jobs/${jobId}/report`);
    if (!reportRes.ok) {
      return NextResponse.json({ error: "Report not found" }, { status: 404 });
    }
    const report = await reportRes.json();

    if (!report.totals || report.totals.analyzed < 3) {
      return NextResponse.json({
        answer:
          "There is not enough analyzed data to answer reliably. This search collected fewer than 3 usable comments. Try enabling more platforms or provide API credentials, then run the search again.",
        insufficient: true,
      });
    }

    // Fetch a representative review sample from the Python API
    const reviewsRes = await fetch(
      `${BACKEND}/api/jobs/${jobId}/reviews?page=1&page_size=12&sort=relevance`,
    );
    let sampleReviews: any[] = [];
    if (reviewsRes.ok) {
      const pag = await reviewsRes.json();
      sampleReviews = pag.items ?? [];
    }
    if (/urdu|roman/i.test(question)) {
      const urduRes = await fetch(
        `${BACKEND}/api/jobs/${jobId}/reviews?page=1&page_size=8&language=roman_urdu&sort=sentiment`,
      );
      if (urduRes.ok) {
        const urdu = (await urduRes.json()).items ?? [];
        sampleReviews = [...sampleReviews, ...urdu.slice(0, 6)];
      }
    }

    const context = buildContext(report, sampleReviews);

    const systemPrompt = [
      "You are the AI Product Research Assistant inside ReviewLens, a review-intelligence platform.",
      "Answer ONLY from the EVIDENCE block below (collected, analyzed comments).",
      "Rules:",
      "1. Never invent reviews, ratings, statistics, or customer opinions.",
      "2. Cite platform names when making platform-specific claims (e.g. 'on Daraz, customers say…').",
      "3. Quote short verbatim snippets (translated to English) when helpful; mention original language.",
      "4. Respect sample-size caveats: low-sample platforms are unreliable; never rank platforms by sentiment alone.",
      "5. If the evidence is insufficient for the question, say exactly that and suggest what data would help.",
      "6. Sentiment percentages describe the analyzed sample, not the whole market; do not present them as ratings or guarantees.",
      "7. If the report is in sample-data mode, disclose that key numbers come from synthetic demonstration data.",
      "8. Be concise (max ~200 words), structured, and helpful; end with an actionable takeaway when possible.",
      "",
      "EVIDENCE:",
      context,
    ].join("\n");

    const zai = await ZAI.create();
    const completion = await zai.chat.completions.create({
      messages: [
        { role: "assistant", content: systemPrompt },
        { role: "user", content: question },
      ],
      thinking: { type: "disabled" },
    });

    const answer = completion.choices[0]?.message?.content?.trim();
    if (!answer) {
      return NextResponse.json({ error: "Empty assistant response" }, { status: 502 });
    }
    return NextResponse.json({ answer });
  } catch (err) {
    console.error("[chat] error:", err);
    return NextResponse.json(
      { error: "Assistant failed to generate an answer. Please try again." },
      { status: 500 },
    );
  }
}
