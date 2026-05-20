import type { ComponentProps } from 'react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

export function Plan2Button({ children, ...props }: ComponentProps<typeof Button>) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex">
            <Button disabled {...props}>
              {children}
            </Button>
          </span>
        </TooltipTrigger>
        <TooltipContent>Available in Plan 2</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
