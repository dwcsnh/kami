"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { RunProvider, useRuns } from "./RunProvider";
import { statusLabels } from "./types";
import s from "./manager.module.css";
import { WorkspaceIcon } from "./WorkspaceIcon";
const links = [
  ["/scenarios", "Kịch bản", "scenario"],
  ["/fleets", "Đội xe & loại xe", "car"],
  ["/metrics", "Kết quả & so sánh", "chart"],
  ["/visualizer", "Bản đồ mô phỏng", "map"],
] as const;
function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { active, live, online, ready } = useRuns();
  const p =
    active && live.runId === active.id
      ? { ...active.progress, ...live.progress }
      : active?.progress;
  const fraction = p?.fraction;
  const current = links.find(
    ([href]) =>
      pathname === href || (href === "/visualizer" && pathname === "/"),
  );
  return (
    <div className={s.shell}>
      <a href="#manager-content" className={s.skip}>
        Đến nội dung
      </a>
      <aside className={s.sidebar}>
        <Link
          href="/scenarios"
          className={s.brand}
          aria-label="kami · Trang kịch bản"
        >
          <span className={s.brandMark}>
            k<span />
          </span>
          <span>
            kami<small>Mobility simulation</small>
          </span>
        </Link>
        <div className={s.workspace}>
          <span className={s.workspaceIcon}>
            <WorkspaceIcon name="leaf" />
          </span>
          <div>
            <strong>Green SM</strong>
            <small>Không gian mô phỏng · Hà Nội</small>
          </div>
        </div>
        <p className={s.navCaption}>KHÔNG GIAN LÀM VIỆC</p>
        <nav aria-label="Điều hướng chính">
          {links.map(([href, label, icon]) => (
            <Link
              key={href}
              href={href}
              aria-label={label}
              title={label}
              aria-current={current?.[0] === href ? "page" : undefined}
            >
              <WorkspaceIcon name={icon} />
              <span>{label}</span>
              <span className={s.mobileLabel}>
                {icon === "scenario"
                  ? "Kịch bản"
                  : icon === "car"
                    ? "Đội xe"
                    : icon === "chart"
                      ? "Kết quả"
                      : "Bản đồ"}
              </span>
              {current?.[0] === href && <span className={s.navDot} />}
            </Link>
          ))}
        </nav>
        <div className={s.sidebarNote}>
          <WorkspaceIcon name="leaf" />
          <strong>
            Thử nghiệm trước.
            <br />
            Vận hành tốt hơn.
          </strong>
          <p>
            Đánh giá kịch bản đội xe và nhu cầu di chuyển trong cùng một không
            gian.
          </p>
        </div>
        <div className={s.sidebarFooter}>
          <span className={s.pulse} />
          kami 0.2<span>Mô phỏng vận hành</span>
        </div>
      </aside>
      <div className={s.mainArea}>
        <header className={s.topbar}>
          <div className={s.breadcrumb}>
            Không gian mô phỏng <span>/</span>{" "}
            <strong>{current?.[1] ?? "Thư viện giao diện"}</strong>
          </div>
          <span className={s.location}>
            <WorkspaceIcon name="map" />
            Hà Nội
          </span>
          <span className={s.connection} data-online={ready && online}>
            <span />
            {!ready
              ? "Đang kết nối…"
              : online
                ? "Backend sẵn sàng"
                : "Mất kết nối backend"}
          </span>
        </header>
        {active && (
          <div className={s.runBanner} role="status" data-testid="active-run">
            <span className={s.pulse} />
            <strong>{active.run_spec.scenario.name}</strong>
            <span>{statusLabels[active.status]}</span>
            <progress
              aria-label="Tiến độ run"
              max={1}
              {...(typeof fraction === "number" ? { value: fraction } : {})}
            />
            <span>
              {typeof fraction === "number"
                ? Math.round(fraction * 100) + "%"
                : "Đang tải…"}
            </span>
            {p?.eta_s != null && (
              <span>Còn khoảng {Math.ceil(p.eta_s)} giây</span>
            )}
            {!online && <span>Chưa xác nhận trạng thái mới</span>}
            <Link href={"/visualizer?run=" + active.id}>
              Mở run #{active.id} →
            </Link>
          </div>
        )}
        {!online && ready && (
          <div className={s.offline} role="status">
            Chưa kết nối được service. Dữ liệu đã lưu vẫn ở database; thao tác
            chạy tạm khoá.
          </div>
        )}
        <div id="manager-content" tabIndex={-1} className={s.content}>
          {children}
        </div>
      </div>
    </div>
  );
}
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <RunProvider>
      <Shell>{children}</Shell>
    </RunProvider>
  );
}
