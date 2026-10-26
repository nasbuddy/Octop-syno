import { Button, Result, Space } from "antd";
import { useTranslation } from "react-i18next";
import { getAppUrl } from "../../api/config";

export default function DsmLogin() {
  const { t } = useTranslation();
  return (
    <Result
      status="403"
      title={t("login.dsm.title")}
      subTitle={t("login.dsm.description")}
      extra={
        <Space>
          <Button type="primary" href="/">
            {t("auth.returnToDsm")}
          </Button>
          <Button href={getAppUrl("/")}>{t("login.dsm.retry")}</Button>
        </Space>
      }
    />
  );
}
