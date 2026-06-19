// 登录页：本地登录表单 + GitHub/Google OAuth 整页跳转 + ?error 展示
import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError } from "@/api/client";
import { login as apiLogin, oauthLoginUrl } from "@/api/auth";
import type { OAuthErrorCode } from "@/types";

// OAuth 回流 ?error 映射到中文提示
const OAUTH_ERROR_TEXT: Record<OAuthErrorCode, string> = {
  oauth_failed: "第三方登录失败，请重试或使用邮箱登录。",
  oauth_unreachable: "登录服务暂不可达，请稍后再试。",
};

export default function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const oauthError = searchParams.get("error") as OAuthErrorCode | null;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await apiLogin({ email, password });
      navigate("/workspaces", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("登录失败，请稍后重试。");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl">登录 MySandbox</CardTitle>
          <CardDescription>
            选择邮箱登录或使用第三方账号继续
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* OAuth 回流错误提示 */}
          {oauthError && OAUTH_ERROR_TEXT[oauthError] && (
            <div
              role="alert"
              className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive"
              data-testid="oauth-error"
            >
              {OAUTH_ERROR_TEXT[oauthError]}
            </div>
          )}
          {/* 本地登录错误提示 */}
          {formError && (
            <div
              role="alert"
              className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive"
              data-testid="form-error"
            >
              {formError}
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <div className="space-y-2">
              <Label htmlFor="email">邮箱</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                data-testid="email-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                data-testid="password-input"
              />
            </div>
            <Button
              type="submit"
              className="w-full"
              disabled={submitting}
              data-testid="login-submit"
            >
              {submitting ? "登录中…" : "登录"}
            </Button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-muted-foreground">或</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <a
              href={oauthLoginUrl("github")}
              className="inline-flex"
              data-testid="oauth-github"
            >
              <Button variant="outline" className="w-full" type="button" asChild>
                <span>GitHub 登录</span>
              </Button>
            </a>
            <a
              href={oauthLoginUrl("google")}
              className="inline-flex"
              data-testid="oauth-google"
            >
              <Button variant="outline" className="w-full" type="button" asChild>
                <span>Google 登录</span>
              </Button>
            </a>
          </div>
        </CardContent>
        <CardFooter className="text-xs text-muted-foreground">
          登录即表示同意 MySandbox 使用条款
        </CardFooter>
      </Card>
    </div>
  );
}
