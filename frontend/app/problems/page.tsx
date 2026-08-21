"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiClient } from "@/services/api-client";
import { StudentHeader } from "@/app/components/student-header";

export default function ProblemsPage() {
  const [problems, setProblems] = useState<any[]>([]);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    apiClient
      .getProblems()
      .then(setProblems)
      .catch(() => setError("Unable to load problems"));
  }, []);
  const problem = problems[index];
  async function submit(event: FormEvent) {
    event.preventDefault();
    setResult(
      await apiClient.submitProblem(problem.id, {
        session_id: crypto.randomUUID(),
        answer,
      }),
    );
  }
  if (error) return <main className="p-8 text-red-600">{error}</main>;
  if (!problem) return <main className="p-8">Loading problem...</main>;
  return (
    <main className="app-page">
      <StudentHeader />
      <div className="max-w-3xl mx-auto p-6">
        <Link href="/dashboard" className="text-blue-600">
          Dashboard
        </Link>
        <div className="flex justify-between items-center mt-8">
          <p className="text-secondary">
            Problem {index + 1} of {problems.length}
          </p>
          <span className="text-sm text-secondary">{problem.difficulty}</span>
        </div>
        <div className="card mt-4">
          <h1 className="text-2xl font-bold">{problem.title}</h1>
          <div
            className="prose dark:prose-invert mt-5"
            dangerouslySetInnerHTML={{ __html: problem.content_html }}
          />
          <form onSubmit={submit} className="mt-8">
            <label className="font-medium">
              Your answer
              <input
                className="input-base mt-2"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Enter a numeric answer"
                required
              />
            </label>
            <button className="btn-primary mt-5">Submit solution</button>
          </form>
          {result && (
            <div
              className={`mt-6 p-4 rounded-lg ${result.is_correct ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800"}`}
            >
              <p className="font-bold">
                {result.is_correct
                  ? `Correct +${result.xp_awarded} XP`
                  : "Not quite yet"}
              </p>
              <p className="mt-2">{result.feedback}</p>
              {index + 1 < problems.length && (
                <button
                  className="mt-4 underline"
                  onClick={() => {
                    setIndex(index + 1);
                    setAnswer("");
                    setResult(null);
                  }}
                >
                  Next problem
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
