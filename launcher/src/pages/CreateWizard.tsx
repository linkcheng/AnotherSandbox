// 多步创建向导：①模板选 minimal ②slug 填写+实时校验 ③确认 ④提交 useCreateWorkspace
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";
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
import { useCreateWorkspace } from "@/api/workspaces";
import { validateSlug } from "@/lib/workspace";
import { ApiError } from "@/api/client";

type Step = 1 | 2 | 3;
const TEMPLATES = [{ id: "minimal", name: "minimal", desc: "最小可用工作区" }];

export default function CreateWizard() {
  const navigate = useNavigate();
  const create = useCreateWorkspace();
  const [step, setStep] = useState<Step>(1);
  const [template, setTemplate] = useState("minimal");
  const [slug, setSlug] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);

  // 自动派生 name：与 slug 一致（最小化设计）
  const name = slug;
  const slugCheck = useMemo(() => validateSlug(slug), [slug]);

  function next() {
    setSubmitError(null);
    if (step === 2 && !slugCheck.ok) return; // 校验不通过不进下一步
    setStep((s) => (s < 3 ? ((s + 1) as Step) : s));
  }
  function prev() {
    setSubmitError(null);
    setStep((s) => (s > 1 ? ((s - 1) as Step) : s));
  }

  async function submit() {
    setSubmitError(null);
    try {
      await create.mutateAsync({ name, slug, template });
      navigate("/workspaces", { replace: true });
    } catch (err) {
      setSubmitError(
        err instanceof ApiError ? err.message : "创建失败，请稍后重试。",
      );
    }
  }

  return (
    <div className="container max-w-2xl py-8">
      <h1 className="mb-6 text-2xl font-semibold">新建工作区</h1>

      <Card>
        <CardHeader>
          <CardTitle>步骤 {step} / 3</CardTitle>
          <CardDescription>
            {step === 1 && "选择模板"}
            {step === 2 && "填写唯一 slug"}
            {step === 3 && "确认信息"}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {submitError && (
            <div
              role="alert"
              className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive"
              data-testid="wizard-error"
            >
              {submitError}
            </div>
          )}

          {step === 1 && (
            <div className="grid gap-3" data-testid="wizard-step-template">
              {TEMPLATES.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTemplate(t.id)}
                  className={`flex items-center justify-between rounded-md border p-4 text-left transition-colors ${
                    template === t.id
                      ? "border-primary bg-accent"
                      : "hover:bg-accent"
                  }`}
                  data-testid={`template-${t.id}`}
                  aria-pressed={template === t.id}
                >
                  <div>
                    <div className="font-medium">{t.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {t.desc}
                    </div>
                  </div>
                  {template === t.id && <Check className="h-4 w-4" />}
                </button>
              ))}
            </div>
          )}

          {step === 2 && (
            <div className="space-y-2" data-testid="wizard-step-slug">
              <Label htmlFor="slug">工作区 slug</Label>
              <Input
                id="slug"
                value={slug}
                onChange={(e) => setSlug(e.target.value.toLowerCase())}
                placeholder="my-sandbox"
                data-testid="slug-input"
                aria-invalid={!slugCheck.ok && slug.length > 0}
              />
              <p className="text-xs text-muted-foreground">
                小写字母、数字与连字符，3-32 位。
              </p>
              {!slugCheck.ok && slug.length > 0 && (
                <p
                  className="text-xs text-destructive"
                  data-testid="slug-error"
                >
                  {slugCheck.reason}
                </p>
              )}
              {slugCheck.ok && (
                <p className="text-xs text-emerald-600" data-testid="slug-ok">
                  slug 可用
                </p>
              )}
            </div>
          )}

          {step === 3 && (
            <dl
              className="space-y-2 text-sm"
              data-testid="wizard-step-confirm"
            >
              <div className="flex justify-between">
                <dt className="text-muted-foreground">模板</dt>
                <dd>{template}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">slug / 名称</dt>
                <dd>
                  <code>{slug}</code>
                </dd>
              </div>
            </dl>
          )}
        </CardContent>

        <CardFooter className="justify-between">
          <Button
            variant="ghost"
            onClick={() => navigate("/workspaces")}
            data-testid="wizard-cancel"
          >
            取消
          </Button>
          <div className="flex gap-2">
            {step > 1 && (
              <Button variant="outline" onClick={prev} data-testid="wizard-prev">
                <ArrowLeft className="h-4 w-4" />
                上一步
              </Button>
            )}
            {step < 3 && (
              <Button
                onClick={next}
                disabled={step === 2 && !slugCheck.ok}
                data-testid="wizard-next"
              >
                下一步
                <ArrowRight className="h-4 w-4" />
              </Button>
            )}
            {step === 3 && (
              <Button
                onClick={submit}
                disabled={create.isPending}
                data-testid="wizard-submit"
              >
                {create.isPending ? "创建中…" : "创建"}
              </Button>
            )}
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}
