"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiClient } from "@/services/api-client";
import { useAuth } from "@/app/providers/auth-context";
import { StudentHeader } from "@/app/components/student-header";
import {
  ActivityIcon,
  ArrowRightIcon,
  BoltIcon,
  FlameIcon,
  GaugeIcon,
  RouteIcon,
  TargetIcon,
} from "@/app/components/ui-icons";

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const [data, setData] = useState<any>(null),
    [error, setError] = useState("");
  const [streakOpen, setStreakOpen] = useState(false),
    [streakTab, setStreakTab] = useState<"personal" | "friends">("personal"),
    [touchStart, setTouchStart] = useState<number | null>(null),
    [streakData, setStreakData] = useState<any>(null),
    [friendUsername, setFriendUsername] = useState(""),
    [friendError, setFriendError] = useState(""),
    [addingFriend, setAddingFriend] = useState(false);
  useEffect(() => {
    if (!loading && user)
      apiClient
        .getStudentDashboard()
        .then(setData)
        .catch(() => setError("Dashboard data could not be loaded."));
  }, [loading, user]);
  if (loading || (user && !data && !error))
    return (
      <main className="app-page grid place-items-center">
        <div className="h-1 w-28 animate-pulse rounded bg-blue-600" />
      </main>
    );
  if (!user)
    return (
      <main className="app-page grid place-items-center">
        <Link href="/login" className="btn-primary">
          Sign in to continue
        </Link>
      </main>
    );
  if (error)
    return (
      <main className="app-page md:pl-[244px]">
        <StudentHeader />
        <div className="mx-auto max-w-6xl p-6">
          <div className="card border-red-200 text-red-700">{error}</div>
        </div>
      </main>
    );
  const stats = data.gamification,
    energy = data.subscription.energy_remaining;
  const levelProgress = Math.max(
    3,
    Math.min(100, 100 - stats.xp_to_next_level),
  );
  const mastery = data.mastery.topics || [];
  const openStreak = async () => {
    setStreakOpen(true);
    setStreakTab("personal");
    setFriendError("");
    try {
      setStreakData(await apiClient.getStreakDetails());
    } catch {
      setFriendError("Data runtunan tidak dapat dimuat.");
    }
  };
  const addFriend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!friendUsername.trim()) return;
    setAddingFriend(true);
    setFriendError("");
    try {
      setStreakData(await apiClient.addStreakFriend(friendUsername));
      setFriendUsername("");
    } catch (err: any) {
      setFriendError(
        err?.response?.data?.detail || "Teman tidak dapat ditambahkan.",
      );
    } finally {
      setAddingFriend(false);
    }
  };
  const today = new Date(),
    monthStart = new Date(today.getFullYear(), today.getMonth(), 1),
    calendarStart = new Date(monthStart);
  calendarStart.setDate(1 - ((monthStart.getDay() + 6) % 7));
  const calendarDays = Array.from({ length: 42 }, (_, index) => {
    const day = new Date(calendarStart);
    day.setDate(calendarStart.getDate() + index);
    return day;
  });
  const activeDates = new Set<string>(streakData?.activity_dates || []);
  const statCards = [
    {
      label: `Level ${stats.level}`,
      value: stats.rank,
      detail: `${stats.total_xp} total XP`,
      progress: levelProgress,
      icon: BoltIcon,
    },
    {
      label: "Current streak",
      value: `${stats.current_streak_days} days`,
      detail: `Longest: ${stats.longest_streak_days || stats.current_streak_days} days`,
      progress: Math.min(100, stats.current_streak_days * 10),
      icon: FlameIcon,
    },
    {
      label: "Learning energy",
      value: energy === null ? "Unlimited" : `${energy} / 10`,
      detail: energy === null ? "Unlimited plan" : "Resets daily",
      progress: energy === null ? 100 : energy * 10,
      icon: ActivityIcon,
    },
    {
      label: "Overall mastery",
      value: `${Math.round(stats.overall_mastery || 0)}%`,
      detail: `${stats.problems_solved} problems solved`,
      progress: stats.overall_mastery || 0,
      icon: GaugeIcon,
    },
  ];
  return (
    <main className="app-page min-h-screen pb-28 md:pl-[244px] md:pb-12">
      <StudentHeader />
      <div className="mx-auto max-w-[1160px] px-4 py-7 sm:px-7 sm:py-10">
        <header>
          <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
            Good to see you, {data.student.full_name.split(" ")[0]}.
          </h1>
          <p className="mt-2 text-slate-500">
            Continue building your electrical engineering skills.
          </p>
        </header>

        <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {statCards.map(({ label, value, detail, progress, icon: Icon }) => (
            <article
              key={label}
              onClick={label === "Current streak" ? openStreak : undefined}
              className={`rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900 ${label === "Current streak" ? "cursor-pointer transition hover:-translate-y-0.5 hover:border-orange-300 hover:shadow-md" : ""}`}
            >
              <div className="flex items-start justify-between">
                <p className="text-[11px] font-black uppercase tracking-[.12em] text-slate-400">
                  {label}
                </p>
                <span
                  className={
                    label === "Current streak"
                      ? "grid h-9 w-9 place-items-center rounded-full bg-orange-50 text-orange-600"
                      : "text-slate-400"
                  }
                >
                  <Icon
                    className={
                      label === "Current streak" ? "h-5 w-5" : "h-4 w-4"
                    }
                  />
                </span>
              </div>
              <p className="mt-3 truncate text-2xl font-black">{value}</p>
              <p className="mt-1 truncate text-xs text-slate-500">
                {label === "Current streak"
                  ? "Buka kalender dan runtunan teman"
                  : detail}
              </p>
              <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                <div
                  className={`h-full rounded-full ${label === "Current streak" ? "bg-orange-500" : "bg-blue-600"}`}
                  style={{ width: `${progress}%` }}
                />
              </div>
            </article>
          ))}
        </section>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <section className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-black uppercase tracking-[.14em] text-slate-400">
                Continue learning
              </p>
              <RouteIcon className="h-5 w-5 text-blue-600" />
            </div>
            <h2 className="mt-5 text-2xl font-black">Your adaptive journey</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              The next 20-question session is selected from your current mastery
              and recent performance.
            </p>
            <div className="mt-6 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div className="h-full w-2/5 rounded-full bg-blue-600" />
            </div>
            <div className="mt-2 flex justify-between text-xs text-slate-400">
              <span>Current learning zone</span>
              <span>Ready</span>
            </div>
            <Link
              href="/journey"
              className="mt-7 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-3 text-sm font-black text-white hover:bg-blue-700"
            >
              Continue journey <ArrowRightIcon className="h-4 w-4" />
            </Link>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-black uppercase tracking-[.14em] text-slate-400">
                Daily engineering quests
              </p>
              <TargetIcon className="h-5 w-5 text-slate-400" />
            </div>
            <div className="mt-5 divide-y divide-slate-100 dark:divide-slate-800">
              {data.quests.length ? (
                data.quests.map((quest: any) => (
                  <div key={quest.id} className="py-4 first:pt-0">
                    <div className="flex items-center gap-3">
                      <span
                        className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border text-xs font-black ${quest.completed ? "border-blue-600 bg-blue-600 text-white" : "border-slate-300 text-slate-400"}`}
                      >
                        {quest.completed ? "✓" : "·"}
                      </span>
                      <strong className="min-w-0 flex-1 text-sm">
                        {quest.name}
                      </strong>
                      <span className="text-xs font-bold text-slate-500">
                        {quest.completed
                          ? "Done"
                          : `${quest.progress}/${quest.target}`}
                      </span>
                    </div>
                    <div className="ml-9 mt-2 h-1 overflow-hidden rounded bg-slate-100 dark:bg-slate-800">
                      <div
                        className="h-full bg-blue-600"
                        style={{
                          width: `${quest.completed ? 100 : Math.min(100, (quest.progress * 100) / quest.target)}%`,
                        }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <p className="py-8 text-sm text-slate-500">
                  New quests will appear here.
                </p>
              )}
            </div>
          </section>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <section className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
            <p className="text-[11px] font-black uppercase tracking-[.14em] text-slate-400">
              Attention needed
            </p>
            {data.recent_errors?.length ? (
              <>
                <h2 className="mt-4 text-xl font-black">
                  {data.recent_errors[0].recommended_review ||
                    "Targeted review available"}
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  A recent answer suggests this area should be reviewed before
                  moving to a harder challenge.
                </p>
                <Link
                  href="/journey"
                  className="mt-5 inline-flex items-center gap-2 text-sm font-black text-blue-600"
                >
                  Start targeted review <ArrowRightIcon className="h-4 w-4" />
                </Link>
              </>
            ) : (
              <>
                <h2 className="mt-4 text-xl font-black">No urgent review</h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  Complete more challenges and ElectroQuest will identify
                  concepts that need attention.
                </p>
              </>
            )}
          </section>
          <section className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
            <p className="text-[11px] font-black uppercase tracking-[.14em] text-slate-400">
              Engineering coach
            </p>
            <h2 className="mt-4 text-xl font-black">Recommended next step</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              {data.next_action}
            </p>
            <Link
              href="/journey"
              className="mt-5 inline-flex items-center gap-2 text-sm font-black text-blue-600"
            >
              Open recommendation <ArrowRightIcon className="h-4 w-4" />
            </Link>
          </section>
        </div>

        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[.14em] text-slate-400">
                Skill mastery
              </p>
              <h2 className="mt-2 text-xl font-black">
                Your strongest signals
              </h2>
            </div>
            <span className="text-xs text-slate-400">
              Based on graded challenges
            </span>
          </div>
          {mastery.length ? (
            <div className="mt-7 grid gap-7 sm:grid-cols-2 xl:grid-cols-4">
              {mastery.slice(0, 4).map((topic: any) => (
                <div key={topic.topic_id}>
                  <div className="flex justify-between gap-3 text-sm">
                    <strong className="truncate">{topic.name}</strong>
                    <span className="font-black">
                      {Math.round(topic.level)}%
                    </span>
                  </div>
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                    <div
                      className="h-full rounded-full bg-blue-600"
                      style={{ width: `${topic.level}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-7 flex items-center gap-4 rounded-lg bg-slate-50 p-5 dark:bg-slate-800">
              <GaugeIcon className="text-slate-400" />
              <p className="text-sm text-slate-500">
                Complete your first challenge to begin measuring skill mastery.
              </p>
            </div>
          )}
        </section>
      </div>
      {streakOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/50 p-0 sm:items-center sm:p-5"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setStreakOpen(false);
          }}
        >
          <section className="max-h-[92vh] w-full max-w-xl overflow-hidden rounded-t-2xl bg-white shadow-2xl dark:bg-slate-900 sm:rounded-2xl">
            <header className="flex items-center justify-between border-b border-slate-200 p-5 sm:p-6 dark:border-slate-800">
              <div className="flex items-center gap-3">
                <span className="grid h-11 w-11 place-items-center rounded-full bg-orange-50 text-orange-600">
                  <FlameIcon className="h-6 w-6" />
                </span>
                <div>
                  <p className="text-xl font-black">Runtunan belajar</p>
                  <p className="text-sm text-slate-500">
                    {stats.current_streak_days} hari berturut-turut
                  </p>
                </div>
              </div>
              <button
                onClick={() => setStreakOpen(false)}
                className="grid h-10 w-10 place-items-center rounded-lg border border-slate-200 text-xl text-slate-500"
                aria-label="Tutup"
              >
                ×
              </button>
            </header>
            <nav className="grid grid-cols-2 border-b border-slate-200 p-2 dark:border-slate-800">
              <button
                onClick={() => setStreakTab("personal")}
                className={`rounded-lg py-3 text-sm font-black ${streakTab === "personal" ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900" : "text-slate-500"}`}
              >
                Personal
              </button>
              <button
                onClick={() => setStreakTab("friends")}
                className={`rounded-lg py-3 text-sm font-black ${streakTab === "friends" ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900" : "text-slate-500"}`}
              >
                Teman
              </button>
            </nav>
            <div
              className="min-h-[430px] touch-pan-y overflow-y-auto p-5 sm:p-6"
              onTouchStart={(e) => setTouchStart(e.touches[0].clientX)}
              onTouchEnd={(e) => {
                if (touchStart === null) return;
                const distance = e.changedTouches[0].clientX - touchStart;
                if (distance > 55) setStreakTab("friends");
                if (distance < -55) setStreakTab("personal");
                setTouchStart(null);
              }}
            >
              {streakTab === "personal" ? (
                <div>
                  <div className="flex items-end justify-between">
                    <div>
                      <p className="text-xs font-black uppercase tracking-widest text-slate-400">
                        Kalender pribadi
                      </p>
                      <h2 className="mt-1 text-xl font-black">
                        {today.toLocaleDateString("id-ID", {
                          month: "long",
                          year: "numeric",
                        })}
                      </h2>
                    </div>
                    <span className="text-xs text-slate-500">
                      Hari aktif ditandai api
                    </span>
                  </div>
                  <div className="mt-6 grid grid-cols-7 gap-2 text-center">
                    {["S", "S", "R", "K", "J", "S", "M"].map((d, i) => (
                      <span
                        key={i}
                        className="pb-1 text-[10px] font-black text-slate-400"
                      >
                        {d}
                      </span>
                    ))}
                    {calendarDays.map((day) => {
                      const local = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`,
                        active = activeDates.has(local),
                        currentMonth = day.getMonth() === today.getMonth();
                      return (
                        <div
                          key={local}
                          className={`relative grid aspect-square place-items-center rounded-lg text-xs font-bold ${active ? "bg-orange-500 text-white" : currentMonth ? "bg-slate-50 text-slate-700 dark:bg-slate-800 dark:text-slate-200" : "text-slate-300 dark:text-slate-700"}`}
                        >
                          {active ? (
                            <FlameIcon className="h-4 w-4" />
                          ) : (
                            day.getDate()
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <p className="mt-5 rounded-lg bg-orange-50 px-4 py-3 text-sm text-orange-900">
                    Kerjakan minimal satu tantangan setiap hari untuk menjaga
                    api tetap menyala.
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-xs font-black uppercase tracking-widest text-slate-400">
                    Runtunan bersama
                  </p>
                  <h2 className="mt-1 text-xl font-black">
                    Belajar dengan teman
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Api bersama bertambah jika kalian berdua aktif pada hari
                    yang sama.
                  </p>
                  <form onSubmit={addFriend} className="mt-5 flex gap-2">
                    <input
                      value={friendUsername}
                      onChange={(e) => setFriendUsername(e.target.value)}
                      placeholder="Username teman"
                      className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-slate-600"
                    />
                    <button
                      disabled={addingFriend}
                      className="rounded-lg bg-slate-900 px-4 text-sm font-black text-white disabled:opacity-50"
                    >
                      Tambah
                    </button>
                  </form>
                  {friendError && (
                    <p className="mt-2 text-xs font-semibold text-red-600">
                      {friendError}
                    </p>
                  )}
                  <div className="mt-5 space-y-3">
                    {streakData?.friends?.length ? (
                      streakData.friends.map((friend: any) => (
                        <div
                          key={friend.id}
                          className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 dark:border-slate-800"
                        >
                          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-slate-100 font-black dark:bg-slate-800">
                            {friend.full_name?.charAt(0) ||
                              friend.username.charAt(0)}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-black">
                              {friend.full_name || friend.username}
                            </p>
                            <p className="truncate text-xs text-slate-500">
                              @{friend.username}
                            </p>
                          </div>
                          <div
                            className={`flex items-center gap-1 font-black ${friend.active_today ? "text-orange-600" : "text-slate-400"}`}
                          >
                            <FlameIcon className="h-5 w-5" />
                            {friend.shared_streak_days}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-xl border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500">
                        Tambahkan teman pertama untuk memulai api bersama.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
            <footer className="border-t border-slate-100 py-3 text-center text-[11px] font-semibold text-slate-400 dark:border-slate-800">
              Geser ke kiri: Personal · Geser ke kanan: Teman
            </footer>
          </section>
        </div>
      )}
    </main>
  );
}
