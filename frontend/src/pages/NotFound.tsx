import { Link } from "react-router";
import { PageHeader } from "../components/layout/PageHeader.tsx";
import { Card } from "../components/ui/Card.tsx";

export default function NotFound() {
  return (
    <>
      <PageHeader title="Halaman tidak ditemukan" />
      <Card>
        <p className="text-body text-ink-muted">
          Alamat ini tidak ada.{" "}
          <Link to="/" className="text-brand underline">
            Kembali ke Dashboard
          </Link>
        </p>
      </Card>
    </>
  );
}
