"use client";

import { TopTape } from "@/components/top-tape";
import { RunConsole } from "@/components/run-console";
import { ActiveRun } from "@/components/active-run";
import { OutputPanel } from "@/components/output-panel";
import { HistoryRail } from "@/components/history-rail";
import { useScraper } from "@/hooks/use-scraper";
import { useExports } from "@/hooks/use-exports";

export default function Dashboard() {
  const {
    form,
    queriesText,
    updateForm,
    setQueries,
    submit,
    isSubmitting,
    submitError,
    viewedJob,
    viewedJobId,
    isViewedRunning,
    isAnyJobRunning,
    elapsed,
    formatElapsed,
    jobs,
    viewJob,
    cancelJob,
    cancelViewedJob,
    cancellingJobId,
    runStateLabel,
  } = useScraper();

  const {
    exports,
    isLoading: exportsLoading,
    refetch: refetchExports,
    downloadFile,
    downloadJobCsv,
    formatBytes,
    formatDate,
  } = useExports();

  return (
    <div className="flex flex-1 flex-col">
      <TopTape runState={runStateLabel} />

      <main className="animate-fade-in mx-auto flex w-full max-w-[1320px] flex-1 flex-col gap-6 px-5 py-6 sm:px-8">
        <RunConsole
          form={form}
          queriesText={queriesText}
          isSubmitting={isSubmitting}
          isRunning={isAnyJobRunning}
          submitError={submitError}
          onUpdateForm={updateForm}
          onSetQueries={setQueries}
          onSubmit={submit}
        />

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex min-w-0 flex-col gap-6">
            <ActiveRun
              job={viewedJob}
              isRunning={isViewedRunning}
              cancelling={
                viewedJob ? cancellingJobId === viewedJob.job_id : false
              }
              elapsed={elapsed}
              formatElapsed={formatElapsed}
              onDownloadCsv={downloadJobCsv}
              onCancel={cancelViewedJob}
            />

            <OutputPanel
              job={viewedJob}
              exports={exports}
              exportsLoading={exportsLoading}
              onRefreshExports={refetchExports}
              onDownloadJobCsv={downloadJobCsv}
              onDownloadFile={downloadFile}
              formatBytes={formatBytes}
              formatDate={formatDate}
            />
          </div>

          <HistoryRail
            jobs={jobs}
            viewedJobId={viewedJobId}
            onViewJob={viewJob}
            onCancelJob={cancelJob}
            cancellingJobId={cancellingJobId}
          />
        </div>
      </main>

      <footer className="border-t border-border/60 px-5 py-4 sm:px-8">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-4">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
            LEADS · SCRAPER
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground/80">
            v1 · Console
          </span>
        </div>
      </footer>
    </div>
  );
}
