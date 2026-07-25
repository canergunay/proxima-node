import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Box,
  Button,
  CircularProgress,
  Divider,
  FormControl,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { DOC_TOPICS } from "../constants/docs";

interface Props {
  onBack: () => void;
}

export default function Docs({ onBack }: Props) {
  const { t } = useTranslation();
  const [slug, setSlug] = useState<string>(DOC_TOPICS[0].slug);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    // Plain fetch (NOT the axios api client — that prefixes /api + JWT).
    // Docs are served as static files from backend/static/docs/<slug>.md.
    fetch(`/docs/${slug}.md`)
      .then((res) => {
        if (!res.ok) throw new Error(t("docs.notFound"));
        return res.text();
      })
      .then(setContent)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [slug, t]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [slug]);

  const currentIndex = DOC_TOPICS.findIndex((topic) => topic.slug === slug);
  const prev = currentIndex > 0 ? DOC_TOPICS[currentIndex - 1] : null;
  const next =
    currentIndex < DOC_TOPICS.length - 1 ? DOC_TOPICS[currentIndex + 1] : null;

  return (
    <Box>
      {/* Header with back button */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
        <IconButton onClick={onBack} aria-label={t("docs.back")} size="small">
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          {t("docs.title")}
        </Typography>
      </Box>

      {/* Mobile topic select — visible only on xs/sm */}
      <FormControl
        fullWidth
        size="small"
        sx={{ display: { xs: "block", md: "none" }, mb: 2 }}
      >
        <Select value={slug} onChange={(e) => setSlug(e.target.value as string)}>
          {DOC_TOPICS.map((topic) => (
            <MenuItem key={topic.slug} value={topic.slug}>
              {topic.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Box sx={{ display: "flex", gap: 3, alignItems: "flex-start" }}>
        {/* Left nav panel — desktop only */}
        <Paper
          variant="outlined"
          sx={{
            display: { xs: "none", md: "block" },
            width: 220,
            flexShrink: 0,
            position: "sticky",
            top: 16,
            maxHeight: "calc(100vh - 90px)",
            overflowY: "auto",
          }}
        >
          <List dense disablePadding>
            {DOC_TOPICS.map((topic) => (
              <ListItemButton
                key={topic.slug}
                selected={slug === topic.slug}
                onClick={() => setSlug(topic.slug)}
                sx={{ py: 0.75 }}
              >
                <ListItemText
                  primary={topic.label}
                  slotProps={{ primary: { sx: { fontSize: "0.85rem" } } }}
                />
              </ListItemButton>
            ))}
          </List>
        </Paper>

        {/* Content area */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {loading ? (
            <Box sx={{ display: "flex", justifyContent: "center", mt: 8 }}>
              <CircularProgress />
            </Box>
          ) : error ? (
            <Box sx={{ mt: 4, textAlign: "center" }}>
              <Typography color="error" variant="h6">
                {error}
              </Typography>
            </Box>
          ) : (
            <>
              <Paper
                variant="outlined"
                sx={{ p: { xs: 2, sm: 3, md: 4 }, maxWidth: 900 }}
              >
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({ children }) => (
                      <Typography
                        variant="h4"
                        gutterBottom
                        sx={{ mt: 1, mb: 2, fontWeight: 600 }}
                      >
                        {children}
                      </Typography>
                    ),
                    h2: ({ children }) => (
                      <Typography
                        variant="h5"
                        gutterBottom
                        sx={{ mt: 4, mb: 1.5, fontWeight: 600 }}
                      >
                        {children}
                      </Typography>
                    ),
                    h3: ({ children }) => (
                      <Typography
                        variant="h6"
                        gutterBottom
                        sx={{ mt: 3, mb: 1, fontWeight: 500 }}
                      >
                        {children}
                      </Typography>
                    ),
                    h4: ({ children }) => (
                      <Typography
                        variant="subtitle1"
                        gutterBottom
                        sx={{ mt: 2, mb: 0.5, fontWeight: 600 }}
                      >
                        {children}
                      </Typography>
                    ),
                    p: ({ children }) => (
                      <Typography
                        variant="body1"
                        sx={{ mb: 1.5, lineHeight: 1.7 }}
                      >
                        {children}
                      </Typography>
                    ),
                    a: ({ href, children }) => {
                      if (href?.startsWith("/docs/")) {
                        const target = href
                          .replace("/docs/", "")
                          .replace(".md", "");
                        return (
                          <Box
                            component="a"
                            href="#"
                            onClick={(e: React.MouseEvent) => {
                              e.preventDefault();
                              setSlug(target);
                            }}
                            sx={{
                              color: "primary.main",
                              textDecoration: "underline",
                              cursor: "pointer",
                              "&:hover": { color: "primary.light" },
                            }}
                          >
                            {children}
                          </Box>
                        );
                      }
                      return (
                        <Box
                          component="a"
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          sx={{
                            color: "primary.main",
                            textDecoration: "underline",
                            "&:hover": { color: "primary.light" },
                          }}
                        >
                          {children}
                        </Box>
                      );
                    },
                    code: ({ className, children }) => {
                      const isBlock = className?.startsWith("language-");
                      if (isBlock) {
                        return (
                          <Paper
                            component="pre"
                            variant="outlined"
                            sx={{
                              p: 2,
                              my: 2,
                              overflow: "auto",
                              bgcolor: "rgba(0,0,0,0.4)",
                              fontFamily: "'Fira Code', 'Consolas', monospace",
                              fontSize: "0.85rem",
                              lineHeight: 1.5,
                              "& code": { background: "none", p: 0 },
                            }}
                          >
                            <code className={className}>{children}</code>
                          </Paper>
                        );
                      }
                      return (
                        <Box
                          component="code"
                          sx={{
                            bgcolor: "rgba(255,255,255,0.08)",
                            px: 0.75,
                            py: 0.25,
                            borderRadius: 0.5,
                            fontFamily: "'Fira Code', 'Consolas', monospace",
                            fontSize: "0.9em",
                          }}
                        >
                          {children}
                        </Box>
                      );
                    },
                    pre: ({ children }) => <>{children}</>,
                    table: ({ children }) => (
                      <Box sx={{ overflowX: "auto", my: 2 }}>
                        <Box
                          component="table"
                          sx={{
                            width: "100%",
                            borderCollapse: "collapse",
                            "& th, & td": {
                              border: "1px solid",
                              borderColor: "divider",
                              px: 1.5,
                              py: 1,
                              fontSize: "0.875rem",
                              textAlign: "left",
                            },
                            "& th": {
                              bgcolor: "rgba(255,255,255,0.05)",
                              fontWeight: 600,
                            },
                          }}
                        >
                          {children}
                        </Box>
                      </Box>
                    ),
                    blockquote: ({ children }) => (
                      <Box
                        sx={{
                          borderLeft: 3,
                          borderColor: "primary.main",
                          pl: 2,
                          my: 2,
                          color: "text.secondary",
                          "& p": { mb: 0.5 },
                        }}
                      >
                        {children}
                      </Box>
                    ),
                    ul: ({ children }) => (
                      <Box
                        component="ul"
                        sx={{ pl: 3, mb: 1.5, "& li": { mb: 0.5 } }}
                      >
                        {children}
                      </Box>
                    ),
                    ol: ({ children }) => (
                      <Box
                        component="ol"
                        sx={{ pl: 3, mb: 1.5, "& li": { mb: 0.5 } }}
                      >
                        {children}
                      </Box>
                    ),
                    hr: () => <Divider sx={{ my: 3 }} />,
                    img: ({ src, alt }) => (
                      <Box
                        component="img"
                        src={src}
                        alt={alt}
                        sx={{
                          maxWidth: "100%",
                          borderRadius: 1,
                          my: 2,
                          display: "block",
                        }}
                      />
                    ),
                  }}
                >
                  {content}
                </ReactMarkdown>
              </Paper>

              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  mt: 2,
                  mb: 4,
                  maxWidth: 900,
                }}
              >
                {prev ? (
                  <Button
                    onClick={() => setSlug(prev.slug)}
                    startIcon={<ArrowBackIcon />}
                    size="small"
                  >
                    {prev.label}
                  </Button>
                ) : (
                  <Box />
                )}
                {next ? (
                  <Button
                    onClick={() => setSlug(next.slug)}
                    endIcon={<ArrowForwardIcon />}
                    size="small"
                  >
                    {next.label}
                  </Button>
                ) : (
                  <Box />
                )}
              </Box>
            </>
          )}
        </Box>
      </Box>
    </Box>
  );
}
