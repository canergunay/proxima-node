import { useEffect, useRef } from "react";
import { Box, Typography, Chip } from "@mui/material";
import { useTranslation } from "react-i18next";

interface Props {
  output: string;
  status: string;
}

const statusColors: Record<string, "success" | "error" | "warning" | "default"> = {
  running: "warning",
  done: "success",
  failed: "error",
  cancelled: "default",
};

// Strip ANSI escape codes
function stripAnsi(text: string): string {
  return text.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "");
}

export default function OutputViewer({ output, status }: Props) {
  const { t } = useTranslation();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [output]);

  const statusKey = `output.${status}` as const;

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1 }}>
        <Typography variant="subtitle2">{t("output.title")}</Typography>
        <Chip
          label={t(statusKey)}
          size="small"
          color={statusColors[status] || "default"}
        />
      </Box>
      <Box
        sx={{
          bgcolor: "#0d1117",
          color: "#c9d1d9",
          fontFamily: "monospace",
          fontSize: 12,
          p: 2,
          borderRadius: 1,
          maxHeight: 400,
          overflow: "auto",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {stripAnsi(output) || (status === "running" ? t("output.running") : "")}
        <div ref={endRef} />
      </Box>
    </Box>
  );
}
