import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { useUpdateCheck } from '@/hooks/useUpdateCheck'
import { UpdateDialog } from '@/features/update/UpdateDialog'

export function UpdateBadge() {
  const { data } = useUpdateCheck()
  const [open, setOpen] = useState(false)

  if (!data?.update_available) return null

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="cursor-pointer">
        <Badge variant="secondary">Update available: v{data.latest}</Badge>
      </button>
      <UpdateDialog open={open} onOpenChange={setOpen} info={data} />
    </>
  )
}
