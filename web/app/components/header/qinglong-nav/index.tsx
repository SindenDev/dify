'use client'

import { useTranslation } from 'react-i18next'
import Link from 'next/link'
import { useSelectedLayoutSegment } from 'next/navigation'
import {
  RiHammerFill,
  RiHammerLine,
} from '@remixicon/react'
import classNames from '@/utils/classnames'
type QinglongNavProps = {
  className?: string
}

const QinglongNav = ({
  className,
}: QinglongNavProps) => {
  const { t } = useTranslation()
  const selectedSegment = useSelectedLayoutSegment()
  const activated = selectedSegment === 'qinglong'

  return (
    <Link href="/qinglong" className={classNames(
      'group text-sm font-medium',
      activated && 'font-semibold bg-components-main-nav-nav-button-bg-active hover:bg-components-main-nav-nav-button-bg-active-hover shadow-md',
      activated ? 'text-components-main-nav-nav-button-text-active' : 'text-components-main-nav-nav-button-text hover:bg-components-main-nav-nav-button-bg-hover',
      className,
    )}>
      {
        activated
          ? <RiHammerFill className='mr-2 w-4 h-4' />
          : <RiHammerLine className='mr-2 w-4 h-4' />
      }
      {t('common.menus.qinglong')}
    </Link>
  )
}

export default QinglongNav
