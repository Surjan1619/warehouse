// Result of the last action on a page: an error or a success note
export const Messages = ({ error, notice }) => (
  <>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="notice" role="status">{notice}</p>}
  </>
);
